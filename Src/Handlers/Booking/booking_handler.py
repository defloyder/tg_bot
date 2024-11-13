from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
from Src.Handlers.Booking.service import generate_calendar
from database import Booking
from database.database import SessionFactory
from database.repository import create_record
from logger_config import logger

router_booking = Router(name="booking")

# Обработчик нажатия кнопки "Записаться"
@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")
    await callback_query.answer()

    master_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Арина", callback_data="master_arina"),
         InlineKeyboardButton(text="Маша", callback_data="master_masha")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text("Выберите мастера:", reply_markup=master_menu)
    logger.debug("Отправлено меню с выбором мастера.")

# Обработчик выбора мастера
@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master(callback_query: CallbackQuery):
    master = callback_query.data.split('_')[1]
    logger.debug(f"Пользователь выбрал мастера: {master}")
    await callback_query.answer()

    try:
        # Генерация календаря
        calendar_markup = await generate_calendar(master)
        await callback_query.message.edit_text("Выберите дату:", reply_markup=calendar_markup)
        logger.debug("Отправлено меню с выбором даты.")
    except Exception as e:
        logger.error(f"Ошибка при генерации календаря для мастера {master}: {e}")
        await callback_query.answer("Произошла ошибка при генерации календаря.", show_alert=True)

# Обработчик выбора даты
@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал дату: {date}, мастер: {master}")
    await callback_query.answer()

    try:
        time_buttons = InlineKeyboardMarkup(row_width=2)

        # Проверка занятости времени
        with SessionFactory() as session:
            busy_times = session.query(Booking.booking_datetime).filter(
                Booking.master == master,
                Booking.booking_datetime.like(f"{date}%")
            ).all()
            busy_times_set = {datetime.strptime(record.booking_datetime, '%Y-%m-%d %H:%M').time() for record in busy_times}

        # Список доступных временных интервалов
        available_times = ["10:00", "11:00", "14:00", "15:00"]
        for hour in available_times:
            hour_time = datetime.strptime(hour, "%H:%M").time()
            if hour_time in busy_times_set:
                time_buttons.add(InlineKeyboardButton(text=f"{hour}❌", callback_data="ignore"))
                logger.info(f"Время {hour} на {date} занято.")
            else:
                time_buttons.add(InlineKeyboardButton(text=hour, callback_data=f"time_{master}_{date}_{hour}"))
                logger.info(f"Время {hour} на {date} доступно.")

        time_buttons.add(InlineKeyboardButton(text="Назад", callback_data=f"master_{master}"))
        await callback_query.message.edit_text(
            f"Выберите время записи на {date} с мастером {master}:",
            reply_markup=time_buttons
        )
        logger.debug("Сообщение с кнопками для выбора времени отправлено.")
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора времени для {master} на {date}: {e}")
        await callback_query.answer("Произошла ошибка при выборе времени.", show_alert=True)

# Обработчик выбора времени для записи
@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master, date, time = data[1], data[2], data[3]
    logger.debug(f"Пользователь выбрал время для записи: {date} {time}, мастер: {master}")
    await callback_query.answer()

    datetime_value = f"{date} {time}"
    try:
        with SessionFactory() as session:
            existing_record = session.query(Booking).filter_by(
                booking_datetime=datetime_value,
                master=master
            ).first()

            if existing_record:
                await callback_query.answer("Это время уже занято.", show_alert=True)
                logger.debug(f"Время {datetime_value} уже занято.")
                return

            # Создаем запись в базе данных
            new_record = create_record(session=session, datetime_value=datetime_value, master=master)
            if not new_record:
                await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
                logger.error(f"Ошибка при создании записи для {datetime_value}.")
                return

            logger.info(f"Запись успешно создана: {new_record}")
    except Exception as e:
        logger.error(f"Ошибка при записи на {datetime_value}: {e}")
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
        return

    # Подтверждение записи
    confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text(
        f"Запись подтверждена!\nМастер: {master}\nДата: {date}\nВремя: {time}",
        reply_markup=confirm_menu
    )
    logger.debug(f"Подтверждение записи отправлено: мастер {master}, дата {date}, время {time}.")
