import calendar
from datetime import datetime, timedelta, date as dt_date

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dateutil.relativedelta import relativedelta
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionFactory
from database.models import MasterSchedule, UserSchedule, Booking
from logger_config import logger

router_schedule = Router(name="master_schedule")


@router_schedule.callback_query(lambda c: c.data == "manage_schedule")
async def manage_schedule(c: CallbackQuery):
    """Начало работы с расписанием мастера."""
    logger.info(f"Обработчик manage_schedule вызван пользователем {c.from_user.id}.")
    try:
        calendar_markup = await generate_schedule_calendar(c.from_user.id)
        if not calendar_markup:
            logger.warning(f"Не удалось сгенерировать календарь для мастера {c.from_user.id}.")
            await c.message.edit_text(
                "Не удалось загрузить расписание. Попробуйте позже.",
                reply_markup=None
            )
            return

        logger.debug(f"Календарь успешно сгенерирован для мастера {c.from_user.id}.")
        await c.message.edit_text(
            "Выберите дату для блокировки/разблокировки:",
            reply_markup=calendar_markup
        )
    except SQLAlchemyError as db_error:
        logger.error(f"Ошибка базы данных при открытии расписания мастера {c.from_user.id}: {db_error}")
        await c.message.edit_text(
            "Произошла ошибка базы данных. Попробуйте позже.",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Неожиданная ошибка при открытии расписания мастера {c.from_user.id}: {e}")
        await c.message.edit_text(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=None
        )


async def generate_schedule_calendar(master_id, month_offset=0):
    """Генерация календаря для управления расписанием с учётом текущего месяца и смещения."""
    now = datetime.now() + relativedelta(months=month_offset)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    start_of_month = dt_date(now.year, now.month, 1)

    month_name = now.strftime('%B %Y')
    calendar_buttons = [[InlineKeyboardButton(text=month_name, callback_data="ignore")]]  # Заголовок месяца

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    week = []

    with SessionFactory() as session:
        try:
            blocked_dates_master = set(
                schedule.day_of_week for schedule in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.is_blocked == True,
                    MasterSchedule.day_of_week >= start_of_month,
                    MasterSchedule.day_of_week <= start_of_month + timedelta(days=days_in_month - 1)
                ).all()
            )

            blocked_dates_user = set(
                schedule.date for schedule in session.query(UserSchedule).filter(
                    UserSchedule.user_id == master_id,
                    UserSchedule.is_blocked == True,
                    UserSchedule.date >= start_of_month,
                    UserSchedule.date <= start_of_month + timedelta(days=days_in_month - 1)
                ).all()
            )

            blocked_dates = blocked_dates_master | blocked_dates_user

            booked_dates = set(
                booking.booking_datetime.date() for booking in session.query(Booking).filter(
                    Booking.master_id == master_id,
                    Booking.status == "new"
                ).all()
            )

            blocked_dates |= booked_dates

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при запросе расписания мастера {master_id}: {e}")
            blocked_dates = set()

    for day in range(1, days_in_month + 1):
        current_date = start_of_month + timedelta(days=day - 1)
        day_str = current_date.strftime('%d')

        if current_date in blocked_dates:
            if current_date in booked_dates:
                week.append(InlineKeyboardButton(text=f"{day_str}📅", callback_data=f"toggle_block_{current_date}"))
            else:
                week.append(InlineKeyboardButton(text=f"{day_str}❌", callback_data=f"toggle_block_{current_date}"))
        elif current_date < datetime.now().date():
            week.append(InlineKeyboardButton(text=f"{day_str}❌", callback_data=f"toggle_block_{current_date}"))
        else:
            week.append(InlineKeyboardButton(text=day_str, callback_data=f"toggle_block_{current_date}"))

        if len(week) == 7:
            calendar_buttons.append(week)
            week = []

    if week:
        calendar_buttons.append(week)

    calendar_buttons.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"prev_month_{month_offset - 1}"),
        InlineKeyboardButton(text="➡️", callback_data=f"next_month_{month_offset + 1}")
    ])
    calendar_buttons.append([InlineKeyboardButton(text="Назад", callback_data="windows")])

    return InlineKeyboardMarkup(inline_keyboard=calendar_buttons)


@router_schedule.callback_query(lambda c: c.data.startswith("toggle_block_"))
async def toggle_block_date(c: CallbackQuery):
    """Переключение блокировки дня у мастера и пользователя."""
    master_id = c.from_user.id
    date_str = c.data.split("_")[2]
    current_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    try:
        with SessionFactory() as session:
            schedule_entry = session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id,
                MasterSchedule.day_of_week == current_date.strftime('%A')
            ).first()

            if schedule_entry:
                logger.debug(f"Запись в MasterSchedule для {current_date}: {schedule_entry}")
            else:
                logger.debug(f"Запись в MasterSchedule для {current_date} не найдена. Создаем новую.")

            if schedule_entry:
                schedule_entry.is_blocked = not schedule_entry.is_blocked
                session.commit()
                status = "заблокирована" if schedule_entry.is_blocked else "разблокирована"
            else:
                new_schedule = MasterSchedule(
                    master_id=master_id,
                    day_of_week=current_date.strftime('%A'),
                    start_time=datetime.min.time(),
                    end_time=datetime.max.time(),
                    is_blocked=True
                )
                session.add(new_schedule)
                session.commit()
                status = "заблокирована"

            user_schedule_entry = session.query(UserSchedule).filter(
                UserSchedule.user_id == master_id,
                UserSchedule.date == current_date
            ).first()

            if user_schedule_entry:
                user_schedule_entry.is_blocked = schedule_entry.is_blocked if schedule_entry else True
                logger.debug(f"Запись в UserSchedule обновлена для {current_date}: {user_schedule_entry}")
            else:
                new_user_schedule = UserSchedule(
                    user_id=master_id,
                    date=current_date,
                    day_of_week=current_date.strftime('%A'),
                    is_blocked=schedule_entry.is_blocked if schedule_entry else True
                )
                session.add(new_user_schedule)
                logger.debug(f"Добавлена новая запись в UserSchedule для {current_date}.")

            session.commit()

            logger.info(f"Дата {current_date} для мастера {master_id} {status}.")
            await c.message.edit_text(
                f"Дата {current_date.strftime('%d.%m.%Y')} успешно {status}.",
                reply_markup=await generate_schedule_calendar(master_id)
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при блокировке {current_date} для мастера {master_id}: {e}")
        await c.message.edit_text("Произошла ошибка базы данных. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при обработке блокировки даты {current_date} для мастера {master_id}: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router_schedule.callback_query(lambda c: c.data.startswith("prev_month_") or c.data.startswith("next_month_"))
async def change_calendar_month(c: CallbackQuery):
    """Смена месяца в календаре."""
    master_id = c.from_user.id

    try:
        command, month_offset_str = c.data.split("_", 1)  # Разделяем на команду и смещение
        month_offset = int(month_offset_str.split("_")[1])

        logger.info(f"Смена месяца для мастера {master_id}: команда {command}, offset {month_offset}")
        calendar_markup = await generate_schedule_calendar(master_id, month_offset)
        await c.message.edit_text(
            "Выберите дату для блокировки/разблокировки:",
            reply_markup=calendar_markup
        )
    except ValueError as e:
        logger.error(f"Ошибка преобразования offset для мастера {master_id}: {e}")
        await c.message.edit_text("Произошла ошибка при обработке команды. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при смене месяца в календаре для мастера {master_id}: {e}")
        await c.message.edit_text("Произошла ошибка при загрузке календаря. Попробуйте позже.")
