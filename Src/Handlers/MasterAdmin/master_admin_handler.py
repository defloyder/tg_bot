import re
from calendar import calendar
from datetime import datetime, date

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master, User
from database.database import SessionFactory
from database.models import MasterSchedule
from logger_config import logger
from menu import main_menu, back_to_master_menu

# Создаём роутер
router_master_admin = Router(name="master_admin")


# Обработчик для кнопки "main_menu"
@router_master_admin.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(c: CallbackQuery):
    """Обработчик для возвращения в главное меню"""
    markup = await main_menu(c.from_user.id)  # Ожидаем объект клавиатуры
    await c.message.edit_text("Вы вернулись в главное меню.", reply_markup=markup)


# Обработчик для кнопки "active_bookings" - Активные записи мастера
@router_master_admin.callback_query(lambda c: c.data == "active_bookings")
async def active_bookings(c: CallbackQuery):
    """Обработчик для отображения активных записей мастера."""
    master_id = c.from_user.id  # Идентифицируем мастера по его user_id
    try:
        with SessionFactory() as session:
            active_bookings = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id
            ).filter(
                Booking.master_id == master_id,
                Booking.status == None,  # Статус "null" - активные записи
                Booking.booking_datetime > datetime.now()  # Дата записи в будущем
            ).all()

            if not active_bookings:
                markup = await main_menu(c.from_user.id)  # Получаем клавиатуру
                await c.message.edit_text("У вас нет активных записей.", reply_markup=markup)
                return

            buttons = [
                [InlineKeyboardButton(
                    text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - Клиент ID: {booking.user_id}",
                    callback_data=f"view_master_booking_{booking.booking_id}"
                )]
                for booking in active_bookings
            ]
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await c.message.edit_text("Ваши активные записи:", reply_markup=markup)

    except Exception as e:
        markup = await main_menu(c.from_user.id)  # Ожидаем клавиатуру
        await c.message.edit_text(f"Произошла ошибка: {str(e)}", reply_markup=markup)

@router_master_admin.callback_query(lambda c: c.data == "booking_history")
async def process_master_history(callback_query: CallbackQuery):
    """Обработчик для кнопки 'История записей' у мастера."""
    master_id = callback_query.from_user.id  # ID мастера
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            # Получаем записи, где master_id совпадает с текущим мастером
            master_history_bookings = session.query(Booking).filter(
                Booking.master_id == master_id,  # Фильтруем по ID мастера
                (Booking.booking_datetime < current_time) |  # Прошедшие записи
                (Booking.status == "cancelled")  # Отменённые записи
            ).order_by(Booking.booking_datetime.desc()).all()

            logger.debug(f"Запрос истории для мастера {master_id}. Количество найденных записей: {len(master_history_bookings)}")

            if not master_history_bookings:
                await callback_query.message.edit_text(
                    "У вас нет прошедших или отменённых записей.",
                    reply_markup=back_to_master_menu()  # Главное меню мастера
                )
                return

            buttons = []
            for booking in master_history_bookings:
                # Получаем информацию о пользователе
                user = session.query(User).filter(User.user_id == booking.user_id).first()
                user_name = user.full_name if user else "Неизвестно"  # Имя пользователя

                # Определяем статус записи
                if booking.status == "cancelled":
                    status = "Отменена"
                elif booking.booking_datetime < current_time:
                    status = "Прошедшая"
                else:
                    status = "Неизвестный статус"

                logger.debug(f"Запись: ID={booking.booking_id}, Статус={status}, Клиент={user_name}, Дата={booking.booking_datetime}")

                # Создаем кнопку для каждой записи
                buttons.append(
                    [InlineKeyboardButton(
                        text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {status} - Клиент: {user_name}",
                        callback_data="ignore"  # Плейсхолдер для кнопки
                    )]
                )

            buttons.append([InlineKeyboardButton(text="Назад", callback_data="master_menu")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            # Отправляем сообщение мастеру
            await callback_query.message.edit_text("Ваша история записей:", reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_master_menu()  # Главное меню мастера
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_master_menu()  # Главное меню мастера
        )


@router_master_admin.callback_query(lambda c: c.data == "windows")
async def windows(c: CallbackQuery):
    """Обработчик для управления окошками мастера."""
    try:
        master_id = c.from_user.id  # Идентифицируем мастера по его user_id
        now = datetime.now()
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Управлять расписанием", callback_data="set_schedule")],
            [InlineKeyboardButton(text="Назад", callback_data="master_menu")]
        ])

        await c.message.edit_text("Выберите действие:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка в обработчике 'windows': {e}")
        markup = await main_menu(c.from_user.id)  # Возврат в главное меню в случае ошибки
        await c.message.edit_text(f"Произошла ошибка: {str(e)}", reply_markup=markup)


@router_master_admin.callback_query(lambda c: c.data.startswith('set_schedule'))
async def set_schedule(callback_query: CallbackQuery):
    """Обработчик для установки расписания мастером."""
    master_id = callback_query.from_user.id
    try:
        with SessionFactory() as session:
            # Получаем текущее расписание мастера
            current_schedule = session.query(MasterSchedule).filter(MasterSchedule.master_id == master_id).all()

        # Если расписание есть, показываем его
        if current_schedule:
            schedule_text = "Ваше текущее расписание:\n"
            for item in current_schedule:
                schedule_text += f"{item.day_of_week}: с {item.start_time} до {item.end_time}\n"
        else:
            schedule_text = "У вас нет установленного расписания. Хотите добавить новое?"

        # Добавляем кнопку для добавления нового времени в расписание
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить расписание", callback_data="add_schedule")],
            [InlineKeyboardButton(text="Назад", callback_data="master_menu")]
        ])

        await callback_query.message.edit_text(schedule_text, reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка при отображении расписания: {e}")
        await callback_query.message.edit_text("Произошла ошибка при получении расписания.")


@router_master_admin.callback_query(lambda c: c.data == "add_schedule")
async def add_schedule(callback_query: CallbackQuery):
    """Обработчик для добавления нового времени в расписание мастера."""
    try:
        master_id = callback_query.from_user.id

        # Даем выбор дня недели
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Понедельник", callback_data="set_day_Monday")],
            [InlineKeyboardButton(text="Вторник", callback_data="set_day_Tuesday")],
            [InlineKeyboardButton(text="Среда", callback_data="set_day_Wednesday")],
            [InlineKeyboardButton(text="Четверг", callback_data="set_day_Thursday")],
            [InlineKeyboardButton(text="Пятница", callback_data="set_day_Friday")],
            [InlineKeyboardButton(text="Суббота", callback_data="set_day_Saturday")],
            [InlineKeyboardButton(text="Воскресенье", callback_data="set_day_Sunday")],
            [InlineKeyboardButton(text="Назад", callback_data="set_schedule")]
        ])

        await callback_query.message.edit_text("Выберите день недели для добавления расписания:", reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка при добавлении расписания: {e}")
        await callback_query.message.edit_text("Произошла ошибка при добавлении расписания.")

@router_master_admin.callback_query(lambda c: c.data.startswith("set_day_"))
async def set_day(callback_query: CallbackQuery):
    """Обработчик для выбора временного интервала на выбранный день недели."""
    day_of_week = callback_query.data.split("_")[2]  # Извлекаем день недели

    # Спрашиваем время начала и окончания работы
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="08:00 - 12:00", callback_data=f"set_time_{day_of_week}_08:00_12:00")],
        [InlineKeyboardButton(text="12:00 - 16:00", callback_data=f"set_time_{day_of_week}_12:00_16:00")],
        [InlineKeyboardButton(text="16:00 - 20:00", callback_data=f"set_time_{day_of_week}_16:00_20:00")],
        [InlineKeyboardButton(text="Назад", callback_data="add_schedule")]
    ])

    await callback_query.message.edit_text(f"Вы выбрали {day_of_week}. Теперь выберите время работы:", reply_markup=markup)

@router_master_admin.callback_query(lambda c: c.data.startswith("set_time_"))
async def set_time(callback_query: CallbackQuery):
    """Обработчик для сохранения временного интервала для выбранного дня недели."""
    try:
        # Разбиваем данные
        data_parts = callback_query.data.split("_")

        # Логируем данные для анализа
        logger.info(f"Полученные данные: {data_parts}")

        # Проверяем, что после split'а получается 5 элементов
        if len(data_parts) != 5:
            logger.error(f"Неверный формат данных: {callback_query.data}")
            await callback_query.answer("Ошибка! Неверный формат данных.", show_alert=True)
            return

        # Извлекаем день недели, время начала и время конца
        _, _, day_of_week, start_time_str, end_time_str = data_parts  # Пропускаем первые два элемента

        # Проверяем и конвертируем только start_time и end_time в объекты времени
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()  # Преобразуем время начала
            end_time = datetime.strptime(end_time_str, '%H:%M').time()  # Преобразуем время конца
        except ValueError:
            # Если произошла ошибка конвертации, например, из-за неправильного формата
            logger.error(f"Некорректное время: {start_time_str} или {end_time_str}")
            await callback_query.answer("Ошибка! Неверный формат времени.", show_alert=True)
            return

        # Логика добавления в базу данных
        master_id = callback_query.from_user.id
        with SessionFactory() as session:
            schedule = MasterSchedule(
                master_id=master_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time
            )
            session.add(schedule)
            session.commit()

        # Ответ на callback_query с учетом того, что запрос мог устареть
        try:
            await callback_query.answer(f"Вы успешно добавили расписание для {day_of_week} с {start_time} до {end_time}.")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка при отправке ответа на callback_query: {e}")
            # Если ответ слишком старый, то отправим новое сообщение вместо ответа на callback_query
            await callback_query.message.edit_text(f"Вы успешно добавили расписание для {day_of_week} с {start_time} до {end_time}.")

    except Exception as e:
        logger.error(f"Ошибка при добавлении времени в расписание: {e}")
        await callback_query.answer("Произошла ошибка при добавлении времени в расписание.", show_alert=True)


@router_master_admin.callback_query(lambda c: c.data == "booking_schedule")
async def booking_schedule(callback_query: CallbackQuery):
    """Обработчик для отображения доступных временных слотов для записи."""
    try:
        master_id = callback_query.from_user.id
        with SessionFactory() as session:
            available_slots = session.query(MasterSchedule).filter(MasterSchedule.master_id == master_id).all()

        if not available_slots:
            await callback_query.message.edit_text("У вас нет доступных временных слотов для записи.")
            return

        calendar_buttons = InlineKeyboardMarkup()

        for slot in available_slots:
            slot_text = f"{slot.day_of_week} с {slot.start_time} до {slot.end_time}"
            callback_data = f"schedule_{slot.schedule_id}"  # Уникальный идентификатор для каждого временного слота
            calendar_buttons.add(InlineKeyboardButton(text=slot_text, callback_data=callback_data))

        calendar_buttons.add(InlineKeyboardButton(text="Назад", callback_data="master_menu"))

        await callback_query.message.edit_text("Выберите время для записи:", reply_markup=calendar_buttons)
    except Exception as e:
        logger.error(f"Ошибка при отображении временных слотов для записи: {e}")
        await callback_query.message.edit_text("Произошла ошибка при получении доступных временных слотов.")

@router_master_admin.callback_query(lambda c: c.data.startswith("schedule_"))
async def choose_schedule(callback_query: CallbackQuery):
    """Обработчик для подтверждения выбора временного интервала для записи."""
    schedule_id = callback_query.data.split("_")[1]
    try:
        # Проверяем, что слот доступен
        with SessionFactory() as session:
            selected_schedule = session.query(MasterSchedule).filter(MasterSchedule.schedule_id == schedule_id).first()

        if selected_schedule:
            # Логика записи (например, создание записи в базе данных)
            await callback_query.message.edit_text(f"Вы записались на {selected_schedule.day_of_week} с {selected_schedule.start_time} до {selected_schedule.end_time}.")
        else:
            await callback_query.message.edit_text("Выбранный слот уже недоступен.")
    except Exception as e:
        logger.error(f"Ошибка при выборе временного интервала: {e}")
        await callback_query.message.edit_text("Произошла ошибка при выборе времени.")
