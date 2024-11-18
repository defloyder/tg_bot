from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from database import Booking
from database.database import SessionFactory
from database.repository import get_booked_dates_for_master
from logger_config import logger

# Генерация календаря для выбора даты
async def generate_calendar(master_id: int):
    now = datetime.now()
    month_str = now.strftime("%B %Y")
    current_month = now.month
    current_day = now.day  # Текущий день месяца

    calendar_buttons = InlineKeyboardBuilder()
    calendar_buttons.add(InlineKeyboardButton(text=month_str, callback_data="ignore", width=7))

    # Добавляем дни недели
    week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    week = []

    # Подготовка списка всех занятых дат для мастера
    try:
        with SessionFactory() as session:
            # Выбираем занятые даты и часы из базы для текущего мастера
            busy_dates = await get_booked_dates_for_master(session, master_id)
            logger.debug(f"Занятые даты для мастера {master_id}: {busy_dates}")
    except Exception as e:
        logger.error(f"Ошибка при запросе занятых дат для мастера {master_id}: {e}")
        busy_dates = set()

    for day in range(1, 32):  # Проходим по всем дням месяца
        try:
            date = datetime(now.year, current_month, day)

            # Если месяц изменился, прекращаем цикл
            if date.month != current_month:
                break

            # Блокируем прошедшие дни
            if date.date() < now.date():  # Если день в прошлом
                week.append(InlineKeyboardButton(text=f"{day}❌", callback_data="ignore", disabled=True))
                continue

            date_str = date.strftime("%d")
            callback_data = f'date_{master_id}_{date.strftime("%d.%m.%Y")}'

            if date.date() in busy_dates:  # Проверяем, занята ли дата
                week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore", disabled=True))
                logger.info(f"Дата {date_str} уже занята.")
            else:
                week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))
                logger.info(f"Дата {date_str} доступна.")

            if len(week) == 7:  # Завершаем строку, когда набрано 7 дней
                calendar_buttons.row(*week)
                week = []
        except ValueError:
            logger.warning(f"Ошибка при обработке дня {day}. Возможно, этого дня нет в месяце.")
            break

    if week:  # Добавляем оставшиеся дни в последнюю строку
        calendar_buttons.row(*week)

    # Кнопка "Назад" для перехода к предыдущему меню
    calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking", width=7))

    return calendar_buttons.as_markup()
