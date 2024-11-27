import calendar
from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.database import SessionFactory
from database.models import MasterSchedule, Booking, UserSchedule
from logger_config import logger


async def generate_calendar(master_id: str):
    """
    Генерация календаря для мастера с отображением занятых и заблокированных дней.
    """
    now = datetime.now()
    now_date = now.date()
    month_str = now.strftime("%B %Y")
    current_month = now.month

    calendar_buttons = InlineKeyboardBuilder()
    calendar_buttons.add(InlineKeyboardButton(text=month_str, callback_data="ignore"))

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    try:
        with SessionFactory() as session:
            blocked_days_master = set(
                schedule.day_of_week for schedule in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.is_blocked == True
                ).all()
            )
            blocked_days_user = set(
                schedule.date for schedule in session.query(UserSchedule).filter(
                    UserSchedule.user_id == master_id,
                    UserSchedule.is_blocked == True
                ).all()
            )
            blocked_dates = blocked_days_master | blocked_days_user

    except Exception as e:
        logger.error(f"Ошибка при запросе блокированных дней для мастера {master_id}: {e}")
        blocked_dates = set()

    days_in_month = calendar.monthrange(now.year, current_month)[1]

    week = []
    day_of_week = datetime(now.year, current_month, 1).weekday()  # День недели для первого числа месяца

    for _ in range(day_of_week):
        week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    for day in range(1, days_in_month + 1):
        try:
            date = datetime(now.year, current_month, day)
            date_str = date.strftime("%d")
            callback_data = f'date_{master_id}_{date.strftime("%Y-%m-%d")}'

            if date.date() <= now_date or date.date() in blocked_dates:
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

    calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking"))
    return calendar_buttons.as_markup()


async def get_booked_times_for_master(session, master_id):
    """
    Получение занятых временных интервалов для мастера.
    """
    blocked_times = {}

    try:
        bookings = session.query(Booking).filter(
            Booking.master_id == master_id,
            Booking.status == "new"
        ).all()

        for booking in bookings:
            start_time = booking.booking_datetime
            end_time = start_time + timedelta(hours=4)
            current_time = start_time

            while current_time < end_time:
                date_key = current_time.date()
                if date_key not in blocked_times:
                    blocked_times[date_key] = set()
                blocked_times[date_key].add(current_time.strftime("%H:%M"))
                current_time += timedelta(minutes=15)

        today_str = datetime.now().date().strftime("%Y-%m-%d")
        if today_str not in blocked_times:
            blocked_times[today_str] = set()

    except Exception as e:
        logger.error(f"Ошибка при запросе занятых временных интервалов для мастера {master_id}: {e}")
        return {}

    logger.debug(f"Занятые временные интервалы для мастера {master_id}: {blocked_times}")
    return blocked_times
