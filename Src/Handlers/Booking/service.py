from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Booking
from database.database import SessionFactory
from logger_config import logger


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

    # Подготовка списка всех занятых дат для мастера
    try:
        with SessionFactory() as session:
            # Выбираем занятые даты и часы из базы для текущего мастера
            busy_dates = session.query(Booking.booking_datetime).filter(Booking.master == master).all()
            busy_days_set = {datetime.strptime(record.booking_datetime, '%Y-%m-%d %H:%M').date() for record in busy_dates}
    except Exception as e:
        logger.error(f"Ошибка при запросе занятых дат для мастера {master}: {e}")
        busy_days_set = set()

    for day in range(1, 32):  # Проходим по всем дням месяца
        try:
            date = datetime(now.year, current_month, day)
            if date.month != current_month:  # Если месяц изменился, прекращаем цикл
                break
            date_str = date.strftime("%d")
            callback_data = f'date_{master}_{date.strftime("%d.%m.%Y")}'

            if date.date() in busy_days_set:  # Проверяем, занята ли дата
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

    calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking", width=7))
    return calendar_buttons.as_markup()
