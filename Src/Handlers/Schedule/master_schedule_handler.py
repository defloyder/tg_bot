import calendar
from sqlalchemy.exc import IntegrityError
from datetime import datetime, time as datetime_time, timedelta  # Используем алиас 'datetime_time'

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
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
    """Генерация календаря для управления расписанием."""
    now = datetime.now() + relativedelta(months=month_offset)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    start_of_month = datetime(now.year, now.month, 1).date()  # Это возвращает объект datetime.date
    first_weekday = start_of_month.weekday()

    month_name = now.strftime('%B %Y')
    calendar_buttons = [[InlineKeyboardButton(text=month_name, callback_data="ignore")]]  # Заголовок месяца

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    week = []

    with SessionFactory() as session:
        try:
            # Собираем заблокированные даты для мастера и пользователя
            blocked_dates_master = set(
                schedule.date for schedule in session.query(MasterSchedule).filter(
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

            blocked_dates = blocked_dates_master | blocked_dates_user  # Объединяем заблокированные даты

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при запросе расписания мастера {master_id}: {e}")
            blocked_dates = set()

    for day in range(1, days_in_month + 1):
        current_date = start_of_month + timedelta(days=day - 1)
        day_str = current_date.strftime('%d')

        if current_date in blocked_dates:
            week.append(InlineKeyboardButton(text=f"{day_str}❌", callback_data=f"toggle_block_{current_date}"))
        elif current_date < datetime.now().date():
            week.append(InlineKeyboardButton(text=f"{day_str}❌", callback_data="ignore"))
        else:
            week.append(InlineKeyboardButton(text=day_str, callback_data=f"toggle_block_{current_date}"))

        if len(week) == 7:
            calendar_buttons.append(week)
            week = []

    if week:
        calendar_buttons.append(week)

    calendar_buttons.append([  # Кнопки перехода между месяцами
        InlineKeyboardButton(text="⬅️", callback_data=f"prev_month_{month_offset - 1}"),
        InlineKeyboardButton(text="➡️", callback_data=f"next_month_{month_offset + 1}")
    ])
    calendar_buttons.append([InlineKeyboardButton(text="Назад", callback_data="windows")])

    return InlineKeyboardMarkup(inline_keyboard=calendar_buttons)


# Общая функция для блокировки/разблокировки дня
async def toggle_day_block(session, master_id, selected_date, block_status):
    """Блокировка или разблокировка всего дня."""
    try:
        # Преобразуем дату в день недели
        day_of_week = selected_date.strftime('%A')

        # Получаем все записи для этого дня
        schedules_to_update = session.query(MasterSchedule).filter(
            MasterSchedule.master_id == master_id,
            MasterSchedule.day_of_week == day_of_week
        ).all()

        # Обновляем все записи на блокирован/разблокирован
        for schedule in schedules_to_update:
            schedule.is_blocked = block_status

        # Обновляем или добавляем запись в UserSchedule
        user_schedule_entry = session.query(UserSchedule).filter(
            UserSchedule.user_id == master_id,
            UserSchedule.date == selected_date
        ).first()

        if user_schedule_entry:
            user_schedule_entry.is_blocked = block_status
        else:
            new_user_schedule = UserSchedule(
                user_id=master_id,
                date=selected_date,
                day_of_week=day_of_week,
                is_blocked=block_status
            )
            session.add(new_user_schedule)

        session.commit()
        return True

    except Exception as e:
        logger.error(f"Ошибка при обновлении блокировки дня {selected_date}: {e}")
        return False


@router_schedule.callback_query(lambda c: c.data.startswith("toggle_block_"))
async def toggle_block_date(c: CallbackQuery):
    """Открытие временных слотов для выбранной даты."""
    master_id = c.from_user.id
    date_str = c.data.split("_")[2]
    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    # Генерация списка временных слотов
    start_time = 10
    end_time = 22
    time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]

    try:
        # Логирование информации о дате и пользователе
        logger.info(f"Загружаем заблокированные слоты для мастера {master_id} на {selected_date}.")

        # Загружаем заблокированные слоты для выбранной даты
        with SessionFactory() as session:
            blocked_slots = set(
                entry.start_time.strftime('%H:%M') for entry in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.day_of_week == selected_date.strftime('%A'),
                    MasterSchedule.is_blocked == True
                ).all()
            )

        # Логирование заблокированных слотов
        logger.debug(f"Заблокированные слоты на {selected_date}: {blocked_slots}")

        # Формируем кнопки для временных слотов
        time_buttons = []
        for time in time_slots:
            if time in blocked_slots:
                # Если слот заблокирован, показываем крестик
                time_buttons.append(InlineKeyboardButton(text=f"❌ {time}", callback_data=f"unblock_time_{selected_date}_{time}"))
            else:
                # Если слот свободен, показываем обычное время
                time_buttons.append(
                    InlineKeyboardButton(text=f"{time}", callback_data=f"block_time_{selected_date}_{time}")
                )

        # Логирование состояния кнопок
        logger.debug(f"Кнопки для слотов на {selected_date}: {[btn.text for btn in time_buttons]}")

        # Проверка блокировки всего дня и добавление кнопки для блокировки/разблокировки дня
        user_schedule_entry = None
        with SessionFactory() as session:
            user_schedule_entry = session.query(UserSchedule).filter(
                UserSchedule.user_id == master_id,
                UserSchedule.date == selected_date
            ).first()

        if user_schedule_entry and user_schedule_entry.is_blocked:
            # Если день заблокирован, меняем текст кнопки на "Открыть день"
            time_buttons.append(InlineKeyboardButton(text="Открыть день", callback_data=f"open_day_{selected_date}"))
        else:
            # Если день не заблокирован, оставляем кнопку "Закрыть день"
            time_buttons.append(InlineKeyboardButton(text="Закрыть день", callback_data=f"close_day_{selected_date}"))

        # Формируем разметку для клавиатуры
        markup = InlineKeyboardMarkup(
            inline_keyboard=[time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)] +
                            [[InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_schedule")]]
        )

        # Логирование разметки
        logger.debug(f"Отправляем клавиатуру с {len(time_buttons)} кнопками.")

        # Отправляем сообщение с клавиатурой
        await c.message.edit_text(f"Выберите время для {selected_date.strftime('%d.%m.%Y')}:",
                                  reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка обработки временных слотов для {selected_date}: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router_schedule.callback_query(lambda c: c.data.startswith("open_day_"))
async def open_day(c: CallbackQuery):
    """Открытие дня: разблокировка всех временных слотов."""
    try:
        # Разбираем дату
        date_str = c.data.split("_")[2]
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        master_id = c.from_user.id

        with SessionFactory() as session:
            success = await toggle_day_block(session, master_id, selected_date, block_status=False)

        if success:
            await c.answer(f"День {selected_date.strftime('%d.%m.%Y')} открыт для мастера.")

            # Перезагружаем календарь
            calendar_markup = await generate_schedule_calendar(master_id)
            await c.message.edit_text(
                "Выберите дату для блокировки/разблокировки:",
                reply_markup=calendar_markup
            )
        else:
            await c.message.edit_text("Произошла ошибка. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Ошибка разблокировки дня {selected_date}: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router_schedule.callback_query(lambda c: c.data.startswith("close_day_"))
async def close_day(c: CallbackQuery):
    """Закрытие дня: блокировка всех временных слотов."""
    try:
        # Разбираем дату
        date_str = c.data.split("_")[2]
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        master_id = c.from_user.id

        with SessionFactory() as session:
            success = await toggle_day_block(session, master_id, selected_date, block_status=True)

        if success:
            await c.answer(f"День {selected_date.strftime('%d.%m.%Y')} заблокирован для мастера.")

            # Перезагружаем календарь
            calendar_markup = await generate_schedule_calendar(master_id)
            await c.message.edit_text(
                "Выберите дату для блокировки/разблокировки:",
                reply_markup=calendar_markup
            )
        else:
            await c.message.edit_text("Произошла ошибка. Попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка блокировки дня {selected_date}: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте позже.")



@router_schedule.callback_query(lambda c: c.data.startswith("block_time_") or c.data.startswith("unblock_time_"))
async def block_hour(c: CallbackQuery):
    """Блокировка/разблокировка временного слота."""
    try:
        # Извлекаем данные из callback_data
        data_parts = c.data.split("_")
        if len(data_parts) < 4:
            logger.error(f"Неверный формат callback_data: {c.data}")
            return

        date_str, hour_str = data_parts[2], data_parts[3]
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        hour = int(hour_str.split(":")[0])  # Извлекаем час

        master_id = c.from_user.id

        # Логирование входных данных
        logger.debug(f"Получена команда для блокировки/разблокировки {selected_date} {hour}:00 от мастера {master_id}")

        # Преобразуем целое число в объект time
        start_time = datetime_time(hour=hour)  # Преобразуем час в объект time
        end_time = datetime_time(hour=hour + 1)  # Конечный час

        with SessionFactory() as session:
            # Проверяем текущий статус (заблокирован или нет)
            schedule_entry = session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id,
                MasterSchedule.start_time == start_time,
                MasterSchedule.day_of_week == selected_date.strftime('%A')
            ).first()

            if schedule_entry:
                logger.debug(f"Текущий статус is_blocked: {schedule_entry.is_blocked}")
                schedule_entry.is_blocked = not schedule_entry.is_blocked
                updated_status = "разблокирован" if not schedule_entry.is_blocked else "заблокирован"
                logger.debug(f"Новый статус is_blocked: {schedule_entry.is_blocked}")
            else:
                # Если записи нет, создаем новую запись для этого времени
                new_schedule = MasterSchedule(
                    master_id=master_id,
                    day_of_week=selected_date.strftime('%A'),
                    start_time=start_time,
                    end_time=end_time,
                    is_blocked=True
                )
                session.add(new_schedule)
                updated_status = "заблокирован"
                logger.info(f"Создана новая запись для {selected_date} {hour}:00 с блокировкой.")

            # Подтверждаем изменения
            session.commit()
            logger.debug("Изменения успешно сохранены в базе данных.")

        # Ответ пользователю
        await c.answer(f"Час {hour}:00 {updated_status} для мастера.")

        # Обновляем клавиатуру, чтобы отобразить новый статус времени
        time_buttons = []
        start_hour = 10
        end_hour = 22
        time_slots = [datetime_time(hour=h).strftime('%H:%M') for h in range(start_hour, end_hour + 1)]

        # Обновляем статусы всех часов
        with SessionFactory() as session:
            blocked_slots = set(
                entry.start_time.strftime('%H:%M') for entry in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.day_of_week == selected_date.strftime('%A'),
                    MasterSchedule.is_blocked == True
                ).all()
            )

        for time_slot in time_slots:
            # Если час заблокирован, показываем "❌", иначе просто время
            if time_slot in blocked_slots:
                time_buttons.append(InlineKeyboardButton(text=f"❌ {time_slot}", callback_data=f"unblock_time_{selected_date}_{time_slot}"))
            else:
                time_buttons.append(InlineKeyboardButton(text=f" {time_slot}", callback_data=f"block_time_{selected_date}_{time_slot}"))

        user_schedule_entry = None
        with SessionFactory() as session:
            user_schedule_entry = session.query(UserSchedule).filter(
                UserSchedule.user_id == master_id,
                UserSchedule.date == selected_date
            ).first()

        if user_schedule_entry and user_schedule_entry.is_blocked:
            time_buttons.append(InlineKeyboardButton(text="Открыть день", callback_data=f"open_day_{selected_date}"))
        else:
            time_buttons.append(InlineKeyboardButton(text="Закрыть день", callback_data=f"close_day_{selected_date}"))

        # Создание новой разметки клавиатуры
        markup = InlineKeyboardMarkup(
            inline_keyboard=[time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)] +
                            [[InlineKeyboardButton(text="⬅️ Назад", callback_data="manage_schedule")]]
        )

        # Отправляем обновленную клавиатуру
        await c.message.edit_text(f"Выберите время для {selected_date.strftime('%d.%m.%Y')}:",
                                  reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка при изменении статуса времени: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте снова.")


@router_schedule.callback_query(lambda c: c.data.startswith("prev_month_") or c.data.startswith("next_month_"))
async def change_calendar_month(c: CallbackQuery):
    """Смена месяца в календаре."""
    master_id = c.from_user.id

    try:
        command, month_offset_str = c.data.split("_", 1)
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
