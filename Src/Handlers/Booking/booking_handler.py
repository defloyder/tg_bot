from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database import Booking
from database.database import SessionFactory
from database.repository import create_record
from logger_config import logger

router_booking = Router(name="booking")


# Генерация календаря для выбора даты
async def generate_calendar(master: str):
    now = datetime.now()
    month_str = now.strftime("%B %Y")
    current_month = now.month

    calendar_buttons = InlineKeyboardBuilder()
    calendar_buttons.add(InlineKeyboardButton(text=month_str, callback_data="ignore", width=7))

    # Добавляем дни недели
    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    week = []
    for day in range(1, 32):
        try:
            date = datetime(now.year, current_month, day)
            if date.month != current_month:
                break
            date_str = date.strftime("%d")
            callback_data = f'date_{master}_{date.strftime("%d.%m.%Y")}'
            logger.debug(f"Проверяем занятость даты {date_str} для мастера {master}.")  # Логирование

            # Проверяем занятость даты в базе
            with SessionFactory() as session:
                existing_record = session.query(Booking).filter_by(
                    booking_datetime=date.strftime('%Y-%m-%d')
                ).first()

            if existing_record:
                week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore"))
                logger.info(f"Дата {date_str} уже занята.")  # Логирование
            else:
                week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))
                logger.info(f"Дата {date_str} доступна.")  # Логирование

            if len(week) == 7:
                calendar_buttons.row(*week)
                week = []
        except ValueError:
            logger.warning(f"Ошибка при обработке дня {day}. Возможно, этого дня нет в месяце.")  # Логирование
            break

    if week:
        calendar_buttons.row(*week)

    calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking", width=7))
    return calendar_buttons.as_markup()


# Обработчик нажатия кнопки "Записаться"
@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")  # Логирование
    await callback_query.answer()

    master_menu = InlineKeyboardMarkup(inline_keyboard=[  # Формируем меню с мастерами
        [InlineKeyboardButton(text="Арина", callback_data="master_arina"),
         InlineKeyboardButton(text="Маша", callback_data="master_masha")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu", width=7)]
    ])
    await callback_query.message.edit_text("Выберите мастера:", reply_markup=master_menu)
    logger.debug("Отправлено меню с выбором мастера.")  # Логирование


# Обработчик выбора мастера
@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master(callback_query: CallbackQuery):
    master = callback_query.data.split('_')[1]
    logger.debug(f"Пользователь выбрал мастера: {master}")  # Логирование
    await callback_query.answer()

    # Генерация календаря и отправка пользователю
    try:
        calendar_markup = await generate_calendar(master)
        await callback_query.message.edit_text("Выберите дату:", reply_markup=calendar_markup)
        logger.debug("Отправлено меню с выбором даты.")  # Логирование
    except Exception as e:
        logger.error(f"Ошибка при генерации календаря для мастера {master}: {e}")  # Логирование ошибки
        await callback_query.answer("Произошла ошибка при генерации календаря.", show_alert=True)


# Обработчик выбора даты
@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master = data[1]
    date = data[2]
    logger.debug(f"Пользователь выбрал дату: {date}, мастер: {master}")  # Логирование
    await callback_query.answer()

    logger.debug(f"Генерация кнопок для выбора времени: {master} {date}")
    try:
        time_buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="10:00", callback_data=f"time_{master}_{date}_10:00"),
             InlineKeyboardButton(text="11:00", callback_data=f"time_{master}_{date}_11:00")],
            [InlineKeyboardButton(text="14:00", callback_data=f"time_{master}_{date}_14:00"),
             InlineKeyboardButton(text="15:00", callback_data=f"time_{master}_{date}_15:00")],
            [InlineKeyboardButton(text="Назад", callback_data=f"master_{master}")]
        ])
        await callback_query.message.edit_text(
            f"Выберите время записи на {date} с мастером {master}:",
            reply_markup=time_buttons
        )
        logger.debug("Сообщение с кнопками для выбора времени отправлено.")  # Логирование
    except Exception as e:
        logger.error(f"Ошибка при отправке кнопок выбора времени для {master} на {date}: {e}")  # Логирование ошибки
        await callback_query.answer("Произошла ошибка при отправке кнопок для выбора времени.", show_alert=True)


# Обработчик выбора времени для записи
@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master, date, time = data[1], data[2], data[3]

    logger.debug(f"Пользователь выбрал время для записи: {date} {time}, мастер: {master}")  # Логирование
    await callback_query.answer()

    datetime_value = f"{date} {time}"

    try:
        with SessionFactory() as session:
            # Проверка на занятость времени
            existing_record = session.query(Booking).filter_by(booking_datetime=datetime_value).first()

            if existing_record:
                await callback_query.answer("Это время уже занято.", show_alert=True)
                logger.debug(f"Время {datetime_value} уже занято.")  # Логирование
                return

            # Попытка создать запись
            new_record = create_record(session=session, datetime_value=datetime_value)
            if new_record:
                logger.debug(f"Запись успешно добавлена в базу данных: {new_record}")  # Логирование
            else:
                await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
                logger.error(f"Ошибка при создании записи для времени {datetime_value}.")  # Логирование
                return
    except Exception as e:
        logger.error(f"Ошибка при обработке времени {datetime_value} для мастера {master}: {e}")  # Логирование ошибки
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)

    # Подтверждение записи
    confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text(
        f"Запись подтверждена! Мастер: {master}, Дата: {date}, Время: {time}",
        reply_markup=confirm_menu
    )
    logger.debug(f"Пользователь подтвердил запись: мастер: {master}, дата: {date}, время: {time}.")  # Логирование
