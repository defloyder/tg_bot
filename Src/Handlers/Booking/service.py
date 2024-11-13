from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database import Booking
from database.database import SessionFactory
from database.repository import create_record
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