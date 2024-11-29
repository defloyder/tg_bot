import re
from datetime import datetime, timedelta

from aiogram import Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from Src.Handlers.Booking.service import generate_calendar
from Src.Handlers.MyBookings.my_bookings_handler import back_to_my_bookings_menu
from database import Booking, Master
from database.database import SessionFactory
from database.models import MasterSchedule
from database.repository import create_booking
from logger_config import logger
from menu import main_menu

scheduler = AsyncIOScheduler()
blocked_times = {}

router_booking = Router(name="booking")
ADMIN_ID = [475953677, 962757762]


@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            masters = session.query(Master).all()

        if not masters:
            await callback_query.message.edit_text("⚠️ *Мастера не найдены. Попробуйте позже.*")
            return

        master_menu = InlineKeyboardMarkup(
            inline_keyboard=[
                                [InlineKeyboardButton(text=f"⚜️ {master.master_name}",
                                                      callback_data=f"booking_master_{master.master_id}")]
                                for master in masters
                            ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]
        )

        await callback_query.message.edit_text("👨‍🔧 *Выберите мастера для записи:*", reply_markup=master_menu)
        logger.debug("Отправлено динамическое меню с выбором мастеров.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка при загрузке списка мастеров: {e}")
        await callback_query.message.edit_text("❌ *Произошла ошибка. Попробуйте позже.*")


@router_booking.callback_query(lambda c: c.data.startswith('booking_master_'))
async def process_callback_master(callback_query: CallbackQuery):
    try:
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 3 or data_parts[0] != "booking" or data_parts[1] != "master":
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("❌ *Некорректные данные. Попробуйте снова.*", show_alert=True)
            return

        master_id = data_parts[2]
        logger.debug(f"Пользователь выбрал мастера с ID: {master_id}")

        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "❌ *Не удалось загрузить календарь. Попробуйте позже.*",
                reply_markup=None
            )
            return

        await callback_query.message.edit_text("📅 *Выберите дату для записи:*", reply_markup=calendar_markup)
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")

    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору даты для мастера {callback_query.data}: {e}")
        await callback_query.answer("❌ *Произошла ошибка при возврате к выбору даты.*", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    try:
        data = callback_query.data.split('_')
        master_id, date = data[1], data[2]
        logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
        await callback_query.answer()

        start_time = 10
        end_time = 22
        time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]  # Время с 10:00 до 22:00

        with SessionFactory() as session:
            selected_date = datetime.strptime(date, '%Y-%m-%d').date()

            bookings = session.query(Booking).filter(
                Booking.master_id == master_id,
                func.date(Booking.booking_datetime) == selected_date
            ).all()

            blocked_times = set()
            for booking in bookings:
                if booking.status != "cancelled":
                    booked_hour = booking.booking_datetime.hour
                    for i in range(0, 4):
                        blocked_hour = booked_hour + i
                        if start_time <= blocked_hour <= end_time:
                            blocked_times.add(f"{blocked_hour:02}:00")

            time_buttons = []
            row = []
            for time in time_slots:
                if time in blocked_times:
                    row.append(InlineKeyboardButton(text=f"❌ {time}", callback_data="ignore"))
                else:
                    row.append(
                        InlineKeyboardButton(text=f"🕒 {time}", callback_data=f"time_{master_id}_{selected_date}_{time}:00"))

                if len(row) == 3:
                    time_buttons.append(row)
                    row = []

            if row:
                time_buttons.append(row)

            time_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"master_{master_id}")])
            await callback_query.message.edit_text(
                "⏰ *Выберите доступное время:*",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=time_buttons)
            )
            logger.debug(f"Доступные временные слоты отправлены пользователю.")
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("❌ *Произошла ошибка при обработке времени.*", show_alert=True)

@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    pattern = r'time_(\d+)_(\d{4}-\d{2}-\d{2})_(\d{2}):(\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, hour, minute = match.groups()
    selected_time = f"{hour}:{minute}"
    user_id = callback_query.from_user.id

    logger.info(f"Пользователь {user_id} выбрал время {selected_time} для мастера {master_id} на дату {date}")

    try:
        with SessionFactory() as session:
            active_booking = session.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.status == "new",
                Booking.booking_datetime > datetime.now()
            ).first()

            if active_booking:
                time_diff = datetime.now() - active_booking.booking_datetime
                if time_diff.days < 7:
                    booking_datetime = active_booking.booking_datetime.strftime('%d.%m.%Y %H:%M')
                    await callback_query.message.edit_text(
                        f"У вас уже есть активная запись на {booking_datetime}. "
                        f"Вы сможете записаться снова через {7 - time_diff.days} дней.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                        )
                    )
                    logger.info(f"Пользователь {user_id} пытался записаться ранее, чем через 7 дней.")
                    return

    except Exception as e:
        logger.error(f"Ошибка при проверке активной записи для пользователя {user_id}: {e}")
        await callback_query.answer("Произошла ошибка при проверке активной записи. Попробуйте позже.", show_alert=True)
        return

    # Перенаправление на выбор минут
    minute_buttons = InlineKeyboardMarkup(
        inline_keyboard=[  # Кнопки минут
            [
                InlineKeyboardButton(text="00 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_00"),
                InlineKeyboardButton(text="15 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_15"),
                InlineKeyboardButton(text="30 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_30"),
                InlineKeyboardButton(text="45 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_45"),
            ],
            [InlineKeyboardButton(text="Назад", callback_data=f"date_{master_id}_{date}")]
        ]
    )

    logger.info(f"Отправлены кнопки выбора минут пользователю {user_id}. Выбранное время: {selected_time}.")

    await callback_query.message.edit_text(
        f"Вы выбрали {selected_time}. Теперь выберите минуты:",
        reply_markup=minute_buttons
    )


@router_booking.callback_query(lambda c: c.data.startswith('minute_'))
async def process_callback_minute(callback_query: CallbackQuery):
    # Паттерн для поиска данных в callback
    pattern = r'minute_(\d+)_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})_(\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, hour, minute, selected_minute = match.groups()
    user_id = callback_query.from_user.id

    selected_time = datetime.strptime(f"{hour}:{minute}", '%H:%M')
    selected_minute = int(selected_minute)  # Выбранные минуты
    final_time = selected_time + timedelta(minutes=selected_minute)

    final_time_str = final_time.strftime('%H:%M')

    logger.info(f"Пользователь {user_id} выбрал время {final_time_str} для мастера {master_id} на дату {date}.")

    try:
        with SessionFactory() as session:
            active_booking = session.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.status == "new",
                Booking.booking_datetime > datetime.now()
            ).first()

            if active_booking:
                time_diff = datetime.now() - active_booking.booking_datetime
                if time_diff.days < 7:
                    booking_datetime = active_booking.booking_datetime.strftime('%d.%m.%Y %H:%M')
                    await callback_query.message.edit_text(
                        f"У вас уже есть активная запись на {booking_datetime}. "
                        f"Вы сможете записаться снова через {7 - time_diff.days} дней.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                        )
                    )
                    logger.info(f"Пользователь {user_id} пытался записаться ранее, чем через 7 дней.")
                    return

    except Exception as e:
        logger.error(f"Ошибка при проверке активной записи для пользователя {user_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
        return

    # Отправка кнопок подтверждения
    confirm_buttons = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Да", callback_data=f"confirm_{master_id}_{date}_{final_time_str}"),
            InlineKeyboardButton(text="Нет", callback_data="cancel_booking")
        ]]
    )

    logger.info(f"Отправлены кнопки подтверждения записи пользователю {user_id}. Время: {final_time_str}.")

    await callback_query.message.edit_text(
        f"Вы выбрали {date} {final_time_str}. Подтвердить?",
        reply_markup=confirm_buttons
    )


@router_booking.callback_query(lambda c: c.data.startswith('confirm_') and not c.data.startswith('confirm_delete_'))
async def process_confirm_time(callback_query: CallbackQuery):
    # Новый паттерн, который также учитывает ситуацию с confirm_delete
    pattern = r'confirm_(\d+)_([\d]{4}-[\d]{2}-[\d]{2})_([\d]{2}:[\d]{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    # Обработка данных, если данные совпали с паттерном
    master_id = match.group(1)
    date = match.group(2)
    time = match.group(3)

    # Преобразуем дату и время в объект datetime
    try:
        booking_datetime = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
    except ValueError as e:
        logger.error(f"Ошибка преобразования даты и времени: {date} {time} — {e}")
        await callback_query.answer("Некорректная дата или время. Попробуйте снова.", show_alert=True)
        return

    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} подтвердил запись на {date} {time}.")

    try:
        with SessionFactory() as session:
            # Проверка на пересечение времени
            overlapping_booking = session.query(Booking).filter(
                Booking.master_id == master_id,
                Booking.status == "new",
                Booking.booking_datetime <= booking_datetime,
                (Booking.booking_datetime + timedelta(hours=4)) > booking_datetime
            ).first()

            if overlapping_booking:
                await callback_query.answer(
                    "⛔ Выбранное время уже занято. Пожалуйста, выберите другое.",
                    show_alert=True
                )
                return

            # Создание нового бронирования
            new_booking = create_booking(
                session=session,
                booking_datetime=booking_datetime,
                master_id=master_id,
                user_id=user_id
            )
            if not new_booking:
                await callback_query.answer("❌ Произошла ошибка при записи.", show_alert=True)
                return

            booking_id = new_booking.booking_id
            master = session.query(Master).filter(Master.master_id == master_id).first()
            master_name = master.master_name if master else "Неизвестно"

            try:
                if master:
                    await callback_query.bot.send_message(
                        master.master_id,
                        f"📅 *У вас новая запись!*\n\n"
                        f"👤 *Пользователь:* {callback_query.from_user.full_name}\n"
                        f"📅 *Дата:* {date}\n"
                        f"⏰ *Время:* {time}",
                        parse_mode="Markdown"
                    )
                    logger.info(f"Уведомление отправлено мастеру {master_name} ({master.master_id}).")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления мастеру {master_id}: {e}")

            await schedule_booking_reminder(booking_datetime, callback_query.bot, user_id, master_name)
            blocked_times.setdefault((master_id, date), set()).add(time)

            # Текст для пользователя
            await callback_query.message.edit_text(
                f"✅ *Запись подтверждена!*\n\n"
                f"📅 *Дата:* {date}\n"
                f"⏰ *Время:* {time}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                        [InlineKeyboardButton(text="💬 Написать мастеру", callback_data=f"write_to_master_{master_id}")]
                    ]
                )
            )

    except Exception as e:
        logger.error(f"Ошибка при подтверждении записи для пользователя {user_id}: {e}")
        await callback_query.answer("❌ Произошла ошибка при записи. Попробуйте позже.", show_alert=True)


async def handle_delete_booking(callback_query, master_id):
    # Логика для удаления бронирования или подтверждения удаления
    logger.info(f"Пользователь запросил удаление записи для мастера {master_id}.")
    await callback_query.answer("Запрос на удаление обработки...")  # Дополнительно - подробности


@router_booking.callback_query(lambda c: c.data == 'cancel_booking')
async def process_cancel_booking(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id  # Получаем ID пользователя из callback_query
    await callback_query.message.edit_text(
        "❌ Создание записи отменено. Вы возвращены в главное меню.",
        reply_markup=await main_menu(user_id)  # Передаем user_id в main_menu
    )


@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master_return(callback_query: CallbackQuery):
    logger.debug(f"Получен callback_data: {callback_query.data}")
    try:
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 2:
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("Некорректные данные. Попробуйте снова.", show_alert=True)
            return

        master_id = data_parts[1]
        logger.debug(f"Пользователь вернулся к выбору даты для мастера с ID: {master_id}")

        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "Не удалось загрузить календарь. Попробуйте позже.",
                reply_markup=None
            )
            return

        await callback_query.message.edit_text(
            "Выберите дату для записи:",
            reply_markup=calendar_markup
        )
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")

    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору даты для мастера {callback_query.data}: {e}")
        await callback_query.answer("Произошла ошибка при возврате к выбору даты.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('edit_booking_'))
async def process_edit_booking(callback_query: CallbackQuery):
    """Обработчик для кнопки 'Редактировать' записи, где мастер остаётся прежним, только дата и время меняются."""
    try:
        booking_id = int(callback_query.data.split("_")[-1])
    except ValueError:
        logger.error(f"Некорректные данные в callback: {callback_query.data}")
        await callback_query.answer("Ошибка обработки данных. Попробуйте снова.", show_alert=True)
        return

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            master_name = session.query(Master.master_name).filter(Master.master_id == booking.master_id).first()
            master_name = master_name[0] if master_name else "Неизвестно"

            old_booking_datetime = booking.booking_datetime.strftime('%d.%m.%Y %H:%M')

            calendar_markup = await generate_calendar(booking.master_id)  # Генерация календаря для старого мастера
            await callback_query.message.edit_text(
                f"Вы выбрали мастера: {master_name}, дата: {old_booking_datetime}\nВыберите новую дату для редактирования записи.",
                reply_markup=calendar_markup)

    except Exception as e:
        logger.error(f"Ошибка при редактировании записи: {e}")
        await callback_query.message.edit_text("Произошла ошибка при редактировании записи. Попробуйте позже.",
                                               reply_markup=back_to_my_bookings_menu())

@router_booking.callback_query(lambda c: c.data.startswith('cancel_booking_'))
async def cancel_booking(callback_query: CallbackQuery):
    try:
        pattern = r'cancel_booking_(\d+)'
        match = re.match(pattern, callback_query.data)

        if not match:
            logger.error(f"Некорректные данные callback: {callback_query.data}")
            await callback_query.answer("❌ Ошибка обработки данных. Попробуйте снова.", show_alert=True)
            return

        booking_id = int(match.group(1))
        user_id = callback_query.from_user.id

        with SessionFactory() as session:
            # Получаем запись по ID
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                logger.warning(f"Попытка отменить несуществующую запись: ID {booking_id}")
                await callback_query.answer("⚠️ Запись не найдена.", show_alert=True)
                return

            if booking.status == "cancelled":
                logger.info(f"Запись ID {booking_id} уже отменена.")
                await callback_query.answer("⚠️ Запись уже отменена.", show_alert=True)
                return

            # Обновляем статус записи
            booking.status = "cancelled"
            session.commit()

            logger.info(f"Запись ID {booking_id} успешно отменена пользователем ID {user_id}.")

            # Сообщение пользователю о том, что запись отменена
            await callback_query.message.edit_text(
                "✅ Ваша запись была успешно отменена.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
                )
            )

            # Уведомление мастеру
            master = session.query(Master).filter(Master.master_id == booking.master_id).first()
            if master:
                try:
                    await callback_query.bot.send_message(
                        master.master_id,
                        f"📅 Запись пользователя {callback_query.from_user.full_name} "
                        f"на {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена.",
                    )
                    logger.info(f"Уведомление отправлено мастеру ID {master.master_id}.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления мастеру {master.master_id}: {e}")

            # Уведомление пользователю (владельцу записи)
            if booking.user_id:
                try:
                    await callback_query.bot.send_message(
                        booking.user_id,
                        f"🔔 Ваша запись на {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена.",
                    )
                    logger.info(f"Уведомление отправлено пользователю ID {booking.user_id}.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю ID {booking.user_id}: {e}")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при отмене записи: {e}")
        await callback_query.answer("❌ Ошибка при отмене записи. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при отмене записи: {e}")
        await callback_query.answer("⚠️ Произошла ошибка. Попробуйте снова.", show_alert=True)


async def send_booking_reminder(bot: Bot, user_id: int, master_name: str, booking_time: datetime):
    try:
        reminder_text = (
            f"⏰ Напоминание: У вас запись к мастеру {master_name} "
            f"на {booking_time.strftime('%d.%m.%Y %H:%M')}. Не забудьте прийти вовремя! "
            "🙏 Будем рады вас увидеть!"
        )
        await bot.send_message(user_id, reminder_text)
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")


async def schedule_booking_reminder(booking_datetime, bot, user_id, master_name):
    # Рассчитать время напоминания
    reminder_time = booking_datetime - timedelta(days=1)
    reminder_time = reminder_time.replace(hour=8, minute=0, second=0, microsecond=0)

    # Если время напоминания уже прошло
    if reminder_time < datetime.now():
        logger.info(
            f"Время напоминания уже прошло ({reminder_time}). "
            f"Отправляем напоминание сразу пользователю {user_id}."
        )
        # Отправить напоминание немедленно
        await send_booking_reminder(bot, user_id, master_name, booking_datetime)
        return

    # Если время напоминания еще не наступило, запланировать его
    job = scheduler.add_job(
        send_booking_reminder,
        'date',
        run_date=reminder_time,
        args=[bot, user_id, master_name, booking_datetime]
    )

    logger.info(f"Напоминание запланировано для пользователя {user_id} на {reminder_time}. Job ID: {job.id}")


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            schedule = session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id
            ).all()
            available_times = []
            for item in schedule:
                available_times.append(f"{item.start_time} - {item.end_time}")

            time_buttons = []
            for time in available_times:
                time_buttons.append([InlineKeyboardButton(text=f"⏰ {time}", callback_data=f"time_{master_id}_{date}_{time}")])

            markup = InlineKeyboardMarkup(inline_keyboard=time_buttons)
            await callback_query.message.edit_text("🕒 Выберите доступное время для записи:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("❌ Произошла ошибка при обработке времени.", show_alert=True)
