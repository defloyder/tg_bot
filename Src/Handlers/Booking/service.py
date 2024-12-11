import calendar
from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.database import SessionFactory
from database.models import MasterSchedule, Booking, UserSchedule
from logger_config import logger
async def generate_calendar(master_id: str, year: int = None, month: int = None):
    """
    Генерация календаря для мастера с возможностью перелистывания вперед.
    """
    now = datetime.now()
    current_date = now.date()
    if not year or not month:
        year, month = now.year, now.month

    month_name = datetime(year, month, 1).strftime("%B %Y")

    calendar_buttons = InlineKeyboardBuilder()
    calendar_buttons.add(InlineKeyboardButton(text=month_name, callback_data="ignore"))

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    try:
        with SessionFactory() as session:
            blocked_dates = set(
                schedule.date for schedule in session.query(UserSchedule).filter(
                    UserSchedule.user_id == master_id,
                    UserSchedule.is_blocked == True
                ).all()
            )

    except Exception as e:
        logger.error(f"Ошибка при запросе блокированных дней для мастера {master_id}: {e}")
        blocked_dates = set()

    days_in_month = calendar.monthrange(year, month)[1]

    week = []
    first_day_weekday = datetime(year, month, 1).weekday()

    for _ in range(first_day_weekday):
        week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    for day in range(1, days_in_month + 1):
        try:
            date = datetime(year, month, day)
            date_str = date.strftime("%d")
            callback_data = f'date_{master_id}_{date.strftime("%Y-%m-%d")}'

            if date.date() <= current_date or date.date() in blocked_dates:
                week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore"))
            else:
                week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))

            if len(week) == 7:
                calendar_buttons.row(*week)
                week = []

        except ValueError:
            logger.warning(f"Ошибка при обработке дня {day}. Возможно, этого дня нет в месяце.")
            break

    if week:
        calendar_buttons.row(*week)

    navigation_buttons = []
    if month == now.month and year == now.year:
        next_month = (month % 12) + 1
        next_year = year + 1 if next_month == 1 else year
        navigation_buttons.append(InlineKeyboardButton(
            text="➡️ Следующий месяц",
            callback_data=f"calendar_{master_id}_{next_year}_{next_month}"
        ))

    elif month == now.month + 1 or (now.month == 12 and month == 1 and year == now.year + 1):
        navigation_buttons.append(InlineKeyboardButton(
            text="⬅️ Текущий месяц",
            callback_data=f"calendar_{master_id}_{now.year}_{now.month}"
        ))

    if navigation_buttons:
        calendar_buttons.row(*navigation_buttons)

    calendar_buttons.row(InlineKeyboardButton(text="⬅ Назад", callback_data="booking"))
    return calendar_buttons.as_markup()
