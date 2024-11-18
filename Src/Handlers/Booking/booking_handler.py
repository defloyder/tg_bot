import asyncio
import re
from aiogram import Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.dialects.mysql import match
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.functions import current_time

from Src.Handlers.Booking.service import generate_calendar
from Src.Handlers.MyBookings.my_bookings_handler import back_to_my_bookings_menu
from database import Booking, Master
from database.database import SessionFactory
from database.repository import create_booking
from logger_config import logger
from menu import ADMIN_ID
from sqlalchemy import func

scheduler = AsyncIOScheduler()

router_booking = Router(name="booking")
ADMIN_ID = 475953677
@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")
    await callback_query.answer()

    master_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Арина", callback_data="booking_master_1"),
         InlineKeyboardButton(text="Маша", callback_data="booking_master_2")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text("Выберите мастера для записи:", reply_markup=master_menu)
    logger.debug("Отправлено меню с выбором мастера.")


@router_booking.callback_query(lambda c: c.data.startswith("booking_master_"))
async def process_callback_master(callback_query: CallbackQuery):
    # Логирование callback данных
    logger.debug(f"Получен callback для записи: {callback_query.data}")

    # Проверяем и разделяем данные callback
    data_parts = callback_query.data.split("_")

    # Убедитесь, что данные соответствуют формату booking_master_{id}
    if len(data_parts) == 3 and data_parts[0] == "booking" and data_parts[1] == "master":
        try:
            # Извлекаем ID мастера
            master_id = int(data_parts[2])
            logger.debug(f"Пользователь выбрал мастера для записи с ID: {master_id}")

            # Генерация календаря
            calendar_markup = await generate_calendar(master_id)
            await callback_query.message.edit_text("Выберите дату для записи:", reply_markup=calendar_markup)
        except ValueError:
            logger.error(f"Некорректный ID мастера: {data_parts[2]}")
            await callback_query.answer("Ошибка обработки данных. Попробуйте снова.", show_alert=True)
    else:
        logger.error(f"Неверный формат данных callback: {callback_query.data}")
        await callback_query.answer("Ошибка обработки данных. Попробуйте снова.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
    await callback_query.answer()

    # Предопределенный список времени
    available_times = ["10:00", "12:00", "14:00", "16:00"]

    try:
        with SessionFactory() as session:
            # Получаем все занятые времена для мастера на выбранный день
            booked_times = {
                booking.booking_datetime.strftime('%H:%M')
                for booking in session.query(Booking.booking_datetime)
                .filter(
                    Booking.master_id == master_id,
                    func.date(Booking.booking_datetime) == datetime.strptime(date, '%d.%m.%Y').date()
                ).all()
            }
            logger.debug(f"Занятые времена для {date}: {booked_times}")

            # Формируем кнопки с учетом занятости
            time_buttons = []
            for time in available_times:
                if time in booked_times:
                    button_text = f"❌ {time}"
                    callback_data = "ignore"  # Делаем кнопку неактивной
                else:
                    button_text = time
                    callback_data = f"time_{master_id}_{date} {time}"
                time_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

            # Кнопка "Назад" для возврата к выбору мастера
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
            # Проверяем существующую запись
            existing_booking = session.query(Booking).filter_by(
                booking_datetime=booking_datetime,
                master_id=master_id,
                user_id=user_id
            ).first()

            if existing_booking:
                # Если запись уже существует, обновляем её
                existing_booking.booking_datetime = booking_datetime
                session.commit()
                logger.info(f"Запись обновлена: {existing_booking}")

                await callback_query.message.edit_text(
                    f"Запись обновлена!\nМастер: {master_id}\nДата: {date}\nВремя: {time}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                    )
                )
            else:
                # Если записи нет, создаем новую
                new_booking = create_booking(session=session, booking_datetime=booking_datetime, master_id=master_id, user_id=user_id)
                if not new_booking:
                    await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
                    logger.error(f"Ошибка при создании записи {booking_datetime}.")
                    return

                # Получаем имя мастера
                master = session.query(Master).filter(Master.master_id == master_id).first()
                master_name = master.master_name if master else "Неизвестно"

                # Планируем уведомление за 24 часа
                asyncio.create_task(
                    schedule_booking_reminder(booking_datetime, callback_query.bot, user_id, master_name))

                await callback_query.message.edit_text(
                    f"Запись подтверждена!\nМастер: {master_name}\nДата: {date}\nВремя: {time}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                    )
                )

    except Exception as e:
        logger.error(f"Ошибка при записи: {e}")
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)

@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master_return(callback_query: CallbackQuery):
    master_id = callback_query.data.split('_')[1]  # Получаем ID мастера
    logger.debug(f"Пользователь вернулся к выбору даты для мастера с ID: {master_id}")
    await callback_query.answer()

    try:
        # Генерация календаря для выбора даты
        calendar_markup = await generate_calendar(master_id)  # Генерация календаря
        await callback_query.message.edit_text("Выберите дату для записи:", reply_markup=calendar_markup)
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")
    except Exception as e:
        logger.error(f"Ошибка при возвращении к выбору даты для мастера {master_id}: {e}")
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
            # Находим старую запись
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            # Получаем имя мастера
            master_name = session.query(Master.master_name).filter(Master.master_id == booking.master_id).first()
            master_name = master_name[0] if master_name else "Неизвестно"

            # Сохраняем информацию о старой записи
            old_booking_datetime = booking.booking_datetime.strftime('%d.%m.%Y %H:%M')

            # Предлагаем пользователю выбрать новую дату и время (мастер остаётся тот же)
            calendar_markup = await generate_calendar(booking.master_id)  # Генерация календаря для старого мастера
            await callback_query.message.edit_text(f"Вы выбрали мастера: {master_name}, дата: {old_booking_datetime}\nВыберите новую дату для редактирования записи.",
                                                   reply_markup=calendar_markup)

    except Exception as e:
        logger.error(f"Ошибка при редактировании записи: {e}")
        await callback_query.message.edit_text("Произошла ошибка при редактировании записи. Попробуйте позже.",
                                                reply_markup=back_to_my_bookings_menu())

@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date_for_editing(callback_query: CallbackQuery):
    """Обработчик для выбора новой даты при редактировании записи."""
    data = callback_query.data.split('_')
    master_id, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал новую дату для редактирования записи: {date}, мастер ID: {master_id}")
    await callback_query.answer()

    # Предопределенный список времени
    available_times = ["10:00", "12:00", "14:00", "16:00"]

    try:
        with SessionFactory() as session:
            # Получаем все занятые времена для мастера на выбранный день
            booked_times = {
                booking.booking_datetime.strftime('%H:%M')
                for booking in session.query(Booking.booking_datetime)
                .filter(
                    Booking.master_id == master_id,
                    func.date(Booking.booking_datetime) == datetime.strptime(date, '%d.%m.%Y').date()
                ).all()
            }
            logger.debug(f"Занятые времена для {date}: {booked_times}")

            # Формируем кнопки с учетом занятости
            time_buttons = []
            for time in available_times:
                if time in booked_times:
                    button_text = f"❌ {time}"
                    callback_data = "ignore"  # Делаем кнопку неактивной
                else:
                    button_text = time
                    callback_data = f"time_{master_id}_{date} {time}"
                time_buttons.append([InlineKeyboardButton(text=button_text, callback_data=callback_data)])

            # Кнопка "Назад" для возврата к выбору мастера
            time_buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"master_{master_id}")])

        time_markup = InlineKeyboardMarkup(inline_keyboard=time_buttons)
        await callback_query.message.edit_text(f"Выберите время для редактирования записи на {date}:", reply_markup=time_markup)
        logger.debug(f"Отправлены кнопки выбора времени для {date} и мастера {master_id}.")

    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("Произошла ошибка при обработке времени.", show_alert=True)
@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time_for_editing(callback_query: CallbackQuery):
    """Обработчик для выбора времени при редактировании записи."""
    pattern = r'time_(\d+)_(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, time = match.groups()
    user_id = callback_query.from_user.id
    logger.debug(f"Пользователь выбрал время для редактирования записи: {date} {time}, мастер ID: {master_id}, пользователь ID: {user_id}")
    await callback_query.answer()

    booking_datetime = datetime.strptime(f"{date} {time}", '%d.%m.%Y %H:%M')

    try:
        with SessionFactory() as session:
            existing_booking = session.query(Booking).filter_by(
                booking_id=callback_query.data.split("_")[-1],
                master_id=master_id,
                user_id=user_id
            ).first()

            if existing_booking:
                existing_booking.booking_datetime = booking_datetime
                session.commit()
                logger.info(f"Запись для пользователя {user_id} обновлена: {existing_booking}")

                await callback_query.message.edit_text(
                    f"Запись обновлена!\nМастер: {master_id}\nДата: {date}\nВремя: {time}",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                    )
                )
            else:
                logger.error(f"Запись для пользователя {user_id} не найдена.")
                await callback_query.answer("Запись не найдена. Попробуйте снова.", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка при обновлении записи: {e}")
        await callback_query.answer("Произошла ошибка при обновлении записи.", show_alert=True)
@router_booking.callback_query(lambda c: c.data.startswith('cancel_booking_'))
async def cancel_booking(callback_query: CallbackQuery):
    """Обработчик для отмены записи."""
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
            # Ищем запись по ID и пользователю
            booking_to_cancel = session.query(Booking).filter(
                Booking.booking_id == booking_id
            ).first()

            if booking_to_cancel:
                # Если пользователь админ, он может отменить любую запись
                if user_id == ADMIN_ID or booking_to_cancel.user_id == user_id:
                    booking_to_cancel.status = "cancelled"
                    session.commit()  # Сохраняем изменения в базе данных
                    logger.info(f"Запись с ID {booking_id} была отменена для пользователя {user_id}.")

                    # Отправляем подтверждение пользователю
                    await callback_query.message.edit_text(
                        f"Ваша запись с ID {booking_id} была успешно отменена.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                        )
                    )
                else:
                    await callback_query.answer("Вы не можете отменить эту запись.", show_alert=True)
                    logger.warning(f"Пользователь {user_id} пытался отменить чужую запись с ID {booking_id}.")
            else:
                logger.error(f"Запись с ID {booking_id} не найдена.")
                await callback_query.answer("Запись не найдена. Вы не можете отменить эту запись.", show_alert=True)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при отмене записи {booking_id}: {e}")
        await callback_query.answer("Произошла ошибка с базой данных. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отмене записи {booking_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

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


async def schedule_booking_reminder(booking_datetime, bot, user_id, master_name):
    """Запланировать отправку напоминания за 24 часа до времени записи в 8:00 утра."""
    reminder_date = booking_datetime - timedelta(days=1)
    reminder_time = reminder_date.replace(hour=8, minute=0, second=0, microsecond=0)
    if reminder_time < datetime.now():
        reminder_time = reminder_time + timedelta(days=1)
    delay = (reminder_time - datetime.now()).total_seconds()
    logger.debug(f"Напоминание запланировано на {reminder_time}. Задержка до отправки: {delay} секунд.")

    if delay > 0:
        await asyncio.sleep(delay)
        await send_booking_reminder(bot, user_id, master_name, booking_datetime)
        logger.info(f"Уведомление отправлено для пользователя {user_id} на {reminder_time}.")
    else:
        logger.warning(f"Напоминание уже прошло для пользователя {user_id}. Мгновенная отправка.")
        await send_booking_reminder(bot, user_id, master_name, booking_datetime)
