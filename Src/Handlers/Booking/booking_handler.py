import asyncio
import re
from datetime import datetime, timedelta

from aiogram import Router, Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, Date
from sqlalchemy.exc import SQLAlchemyError

from Src.Handlers.Booking.service import generate_calendar
from Src.Handlers.MyBookings.my_bookings_handler import back_to_my_bookings_menu
from database import Booking, Master
from database.database import SessionFactory
from database.repository import create_booking
from logger_config import logger
from menu import main_menu

scheduler = AsyncIOScheduler()

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
            await callback_query.message.edit_text("Мастера не найдены. Попробуйте позже.")
            return

        master_menu = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=master.master_name, callback_data=f"booking_master_{master.master_id}")]
                for master in masters
            ] + [[InlineKeyboardButton(text="Назад", callback_data="main_menu")]]
        )

        await callback_query.message.edit_text("Выберите мастера для записи:", reply_markup=master_menu)
        logger.debug("Отправлено динамическое меню с выбором мастеров.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка при загрузке списка мастеров: {e}")
        await callback_query.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router_booking.callback_query(lambda c: c.data.startswith('booking_master_'))
async def process_callback_master(callback_query: CallbackQuery):
    try:
        # Проверка и извлечение master_id
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 3 or data_parts[0] != "booking" or data_parts[1] != "master":
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("Некорректные данные. Попробуйте снова.", show_alert=True)
            return

        master_id = data_parts[2]  # Строка master_id
        logger.debug(f"Пользователь выбрал мастера с ID: {master_id}")

        # Генерация календаря для мастера
        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "Не удалось загрузить календарь. Попробуйте позже.",
                reply_markup=None
            )
            return

        # Отправка календаря
        await callback_query.message.edit_text("Выберите дату для записи:", reply_markup=calendar_markup)
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")

    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору даты для мастера {callback_query.data}: {e}")
        await callback_query.answer("Произошла ошибка при возврате к выбору даты.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
    await callback_query.answer()

    available_times = ["10:00", "12:00", "14:00", "16:00"]

    try:
        with SessionFactory() as session:
            booked_times = {
                booking.booking_datetime.strftime('%H:%M')
                for booking in session.query(Booking.booking_datetime)
                .filter(
                    Booking.master_id == master_id,
                    func.date(Booking.booking_datetime) == datetime.strptime(date, '%d.%m.%Y').date()
                ).all()
            }

            booking_statuses = {
                booking.booking_datetime.strftime('%H:%M'): booking.status
                for booking in session.query(Booking).filter(
                    Booking.master_id == master_id,
                    func.date(Booking.booking_datetime) == datetime.strptime(date, '%d.%m.%Y').date()
                ).all()
            }

            time_buttons = []
            for time in available_times:
                status = booking_statuses.get(time)
                if time in booked_times:
                    if status == "cancelled":

                        button_text = f"{time}"
                        callback_data = f"time_{master_id}_{date} {time}"
                    else:

                        button_text = f"❌ {time}"
                        callback_data = "ignore"
                else:

                    button_text = time
                    callback_data = f"time_{master_id}_{date} {time}"

                time_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

            markup = InlineKeyboardMarkup(inline_keyboard=time_buttons)
            await callback_query.message.edit_text(
                "Выберите доступное время:",
                reply_markup=markup
            )

            time_buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"master_{master_id}")])

        time_markup = InlineKeyboardMarkup(inline_keyboard=time_buttons)
        await callback_query.message.edit_text(f"Выберите время для записи на {date}:", reply_markup=time_markup)
        logger.debug(f"Отправлены кнопки выбора времени для {date} и мастера {master_id}.")
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("Произошла ошибка при обработке времени.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    pattern = r'time_(\d+)_(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, time = match.groups()
    user_id = callback_query.from_user.id
    booking_datetime = datetime.strptime(f"{date} {time}", '%d.%m.%Y %H:%M')

    try:
        with SessionFactory() as session:
            active_booking = session.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.status == "new",  # Статус "new" означает активную запись
                Booking.booking_datetime > datetime.now()  # Запись должна быть в будущем
            ).first()

            if active_booking:
                # Проверяем, прошло ли 2 недели с момента записи
                time_diff = datetime.now() - active_booking.booking_datetime
                if time_diff.days < 14:
                    await callback_query.answer(
                        "У вас уже есть активная запись. Вы можете либо отменить её, либо подождать 2 недели, чтобы записаться снова.",
                        show_alert=True
                    )
                    return
                else:
                    # Если прошло больше 2 недель, можно записаться
                    pass

            # Создаём новую запись
            new_booking = create_booking(session=session, booking_datetime=booking_datetime, master_id=master_id,
                                         user_id=user_id)
            if not new_booking:
                await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
                logger.error(f"Ошибка при создании записи {booking_datetime}.")
                return

            # Используем правильное имя для booking_id
            booking_id = new_booking.booking_id  # Исправлено на booking_id

            master = session.query(Master).filter(Master.master_id == master_id).first()
            master_name = master.master_name if master else "Неизвестно"

            # Уведомление мастеру сразу после создания записи
            if master:
                try:
                    await callback_query.bot.send_message(
                        master.master_id,
                        f"*У вас новая запись!* \n\n*Пользователь:* {callback_query.from_user.full_name}\n*Дата:* {date}\n*Время:* {time}",
                        parse_mode="Markdown",
                        reply_markup=None
                    )
                    logger.info(f"Уведомление отправлено мастеру {master.master_name} ({master.master_id}).")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления мастеру {master.master_id}: {e}")

            # Отложенное напоминание о записи
            asyncio.create_task(
                schedule_booking_reminder(booking_datetime, callback_query.bot, user_id, master_name, session, booking_id)
            )

            await callback_query.message.edit_text(
                f"*Запись подтверждена!*\n\n*Мастер:* {master_name}\n*Дата:* {date}\n*Время:* {time}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")],
                        [InlineKeyboardButton(text="Написать мастеру", callback_data=f"write_to_master_{master_id}")]
                    ]
                )
            )
    except Exception as e:
        logger.error(f"Ошибка при записи: {e}")
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master_return(callback_query: CallbackQuery):
    logger.debug(f"Получен callback_data: {callback_query.data}")
    try:
        # Проверка и извлечение master_id
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 2:
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("Некорректные данные. Попробуйте снова.", show_alert=True)
            return

        master_id = data_parts[1]  # Оставляем как строку
        logger.debug(f"Пользователь вернулся к выбору даты для мастера с ID: {master_id}")

        # Генерация календаря
        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "Не удалось загрузить календарь. Попробуйте позже.",
                reply_markup=None
            )
            return

        # Отправка календаря
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
        booking_id = int(callback_query.data.split("_")[-1])  # Извлекаем ID записи
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


# @router_booking.callback_query(lambda c: c.data.startswith('time_'))
# async def process_callback_time_for_editing(callback_query: CallbackQuery):
#     """Обработчик для выбора времени при редактировании записи."""
#     pattern = r'time_(\d+)_(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2})'
#     match = re.match(pattern, callback_query.data)
#
#     if not match:
#         logger.error(f"Некорректные данные callback: {callback_query.data}")
#         await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
#         return
#
#     master_id, date, time = match.groups()
#     user_id = callback_query.from_user.id
#     logger.debug(
#         f"Пользователь выбрал время для редактирования записи: {date} {time}, мастер ID: {master_id}, пользователь ID: {user_id}")
#     await callback_query.answer()
#
#     booking_datetime = datetime.strptime(f"{date} {time}", '%d.%m.%Y %H:%M')
#
#     try:
#         with SessionFactory() as session:
#             existing_booking = session.query(Booking).filter_by(
#                 booking_id=callback_query.data.split("_")[-1],
#                 master_id=master_id,
#                 user_id=user_id
#             ).first()
#
#             if existing_booking:
#                 existing_booking.booking_datetime = booking_datetime
#                 session.commit()
#                 logger.info(f"Запись для пользователя {user_id} обновлена: {existing_booking}")
#
#                 await callback_query.message.edit_text(
#                     f"Запись обновлена!\nМастер: {master_id}\nДата: {date}\nВремя: {time}",
#                     reply_markup=InlineKeyboardMarkup(
#                         inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
#                     )
#                 )
#             else:
#                 logger.error(f"Запись для пользователя {user_id} не найдена.")
#                 await callback_query.answer("Запись не найдена. Попробуйте снова.", show_alert=True)
#
#     except Exception as e:
#         logger.error(f"Ошибка при обновлении записи: {e}")
#         await callback_query.answer("Произошла ошибка при обновлении записи.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('cancel_booking_'))
async def cancel_booking(callback_query: CallbackQuery):
    """Обработчик для отмены записи (пользовательская версия)."""
    pattern = r'cancel_booking_(\d+)'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    booking_id = match.group(1)
    user_id = callback_query.from_user.id
    logger.debug(f"Пользователь с ID {user_id} запросил отмену записи с ID {booking_id}")

    try:
        with SessionFactory() as session:
            # Получаем запись из базы данных
            booking = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id,
                Master.master_name,
                Booking.status,
                Booking.master_id
            ).join(Master).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.answer("Запись с таким ID не найдена.", show_alert=True)
                logger.error(f"Запись с ID {booking_id} не найдена для отмены.")
                return

            # Проверка, отменена ли уже запись
            if booking.status == "cancelled":
                await callback_query.answer("Запись уже отменена.", show_alert=True)
                return

            # Обновляем статус записи на "cancelled"
            session.execute(
                Booking.__table__.update().where(Booking.booking_id == booking_id).values(status="cancelled")
            )
            session.commit()

            master_name = booking.master_name
            booking_datetime = booking.booking_datetime
            master_id = booking.master_id

            # Отправляем уведомление пользователю
            try:
                if booking.user_id:
                    await callback_query.bot.send_message(
                        booking.user_id,
                        f"Ваша запись к мастеру {master_name} на {booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена.",
                        reply_markup=None
                    )
                    logger.info(f"Уведомление отправлено пользователю {booking.user_id}.")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {booking.user_id}: {e}")

            # Уведомление мастеру о том, что запись была отменена
            if master_id:
                try:
                    await callback_query.bot.send_message(
                        master_id,
                        f"Запись пользователя {booking.user_id} на {booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена.",
                        reply_markup=None
                    )
                    logger.info(f"Уведомление отправлено мастеру {master_name} ({master_id}).")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления мастеру {master_id}: {e}")

            # Ответ пользователю
            await callback_query.answer("Запись успешно отменена.")
            await callback_query.message.edit_text(
                f"Ваша запись с ID {booking_id} была успешно отменена.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                )
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
            )
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
            )
        )


async def send_booking_reminder(bot: Bot, user_id: int, master_name: str, booking_time: datetime):
    """Функция для отправки напоминания пользователю о записи."""
    try:
        reminder_text = (
            f"Напоминание: У вас запись к мастеру {master_name} "
            f"на {booking_time.strftime('%d.%m.%Y %H:%M')}. Не забудьте прийти вовремя!"
        )
        await bot.send_message(user_id, reminder_text)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")


async def schedule_booking_reminder(booking_datetime, bot, user_id, master_name, session, booking_id):
    """Запланировать отправку напоминания за 24 часа до времени записи в 8:00 утра."""
    reminder_date = booking_datetime - timedelta(days=1)
    reminder_time = reminder_date.replace(hour=8, minute=0, second=0, microsecond=0)

    if reminder_time < datetime.now():
        reminder_time = reminder_time + timedelta(days=1)

    delay = (reminder_time - datetime.now()).total_seconds()
    logger.debug(f"Напоминание запланировано на {reminder_time}. Задержка до отправки: {delay} секунд.")

    if delay > 0:
        job = scheduler.add_job(
            send_booking_reminder, 'date', run_date=reminder_time, args=[bot, user_id, master_name, booking_datetime]
        )

        # Сохраняем job_id в базе данных
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()
            if booking:
                booking.reminder_job_id = job.id  # Сохраняем ID задачи напоминания
                session.commit()

        logger.info(f"Напоминание запланировано для пользователя {user_id} на {reminder_time}. Job ID: {job.id}")
    else:
        logger.warning(f"Напоминание уже прошло для пользователя {user_id}. Мгновенная отправка.")
        await send_booking_reminder(bot, user_id, master_name, booking_datetime)

