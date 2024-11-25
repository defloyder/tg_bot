import calendar
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.database import SessionFactory
from database.repository import get_booked_dates_for_master
from logger_config import logger

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from menu import main_menu


async def generate_calendar(master_id: str):
    now = datetime.now()
    month_str = now.strftime("%B %Y")
    current_month = now.month

    # Создаем объект для кнопок
    calendar_buttons = InlineKeyboardBuilder()
    calendar_buttons.add(InlineKeyboardButton(text=month_str, callback_data="ignore"))

    # Добавляем дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    try:
        # Получаем занятые даты для мастера
        with SessionFactory() as session:
            busy_dates = await get_booked_dates_for_master(session, master_id)
            logger.debug(f"Занятые даты для мастера {master_id}: {busy_dates}")
    except Exception as e:
        logger.error(f"Ошибка при запросе занятых дат для мастера {master_id}: {e}")
        busy_dates = set()

    # Определяем количество дней в текущем месяце
    days_in_month = calendar.monthrange(now.year, current_month)[1]

    # Начинаем формировать календарь
    week = []
    day_of_week = datetime(now.year, current_month, 1).weekday()  # Определяем день недели для первого числа месяца

    for _ in range(day_of_week):
        week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    # Добавляем дни месяца
    for day in range(1, days_in_month + 1):
        try:
            date = datetime(now.year, current_month, day)

            if date.date() < now.date():  # Если день в прошлом
                week.append(InlineKeyboardButton(text=f"{day}❌", callback_data="ignore"))
            elif date.date() == now.date():  # Для текущего дня
                if now.hour >= 0:  # Если текущее время уже прошло, ставим крестик
                    week.append(InlineKeyboardButton(text=f"{day}❌", callback_data="ignore"))
                else:
                    date_str = date.strftime("%d")
                    callback_data = f'date_{master_id}_{date.strftime("%d.%m.%Y")}'
                    if date.date() in busy_dates:
                        week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore"))
                    else:
                        week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))
            else:  # Для будущих дней
                date_str = date.strftime("%d")
                callback_data = f'date_{master_id}_{date.strftime("%d.%m.%Y")}'
                if date.date() in busy_dates:
                    week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore"))
                else:
                    week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))

            # Завершаем строку недели, если 7 кнопок
            if len(week) == 7:
                calendar_buttons.row(*week)
                week = []  # Сбрасываем неделю для следующей

        except ValueError:
            logger.warning(f"Ошибка при обработке дня {day}. Возможно, этого дня нет в месяце.")
            break

    # Если в текущей неделе осталось меньше 7 дней, добавляем их
    if week:
        calendar_buttons.row(*week)

    # Добавляем кнопку "Назад", которая будет вести к главному меню
    calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking", width=7))

    return calendar_buttons.as_markup()
