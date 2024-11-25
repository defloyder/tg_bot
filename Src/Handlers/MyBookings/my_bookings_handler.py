import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master, User  # Модели таблицы записей и мастеров
from database.database import SessionFactory
from menu import my_bookings_menu

logger = logging.getLogger(__name__)

router_bookings = Router(name="bookings")


@router_bookings.callback_query(lambda c: c.data == "my_bookings")
async def process_my_bookings(callback_query: CallbackQuery):
    """Обработчик для кнопки 'Мои записи'."""
    await callback_query.answer()
    await callback_query.message.edit_text("Выберите опцию:", reply_markup=my_bookings_menu())


@router_bookings.callback_query(lambda c: c.data == "active_bookings")
async def process_active_bookings(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            # Проверяем, является ли пользователь мастером
            is_master = session.query(Master).filter(Master.master_id == user_id).first()

            if is_master:
                # Для мастера запрос активных записей
                active_bookings = session.query(Booking).filter(
                    Booking.master_id == user_id,
                    Booking.status == 'new',
                    Booking.booking_datetime > current_time
                ).order_by(Booking.booking_datetime).all()
            else:
                # Для обычного пользователя запрос активных записей
                active_bookings = session.query(Booking).filter(
                    Booking.user_id == user_id,
                    Booking.status == 'new',
                    Booking.booking_datetime > current_time
                ).order_by(Booking.booking_datetime).all()

            # Обрабатываем результат
            if not active_bookings:
                await callback_query.message.edit_text(
                    "У вас нет активных записей.",
                    reply_markup=back_to_my_bookings_menu()  # Используем кнопки для возвращения в "Мои записи"
                )
                return

            # Создаем кнопки для активных записей
            buttons = []
            for booking in active_bookings:
                if is_master:
                    # Для мастера показываем имя клиента
                    user = session.query(User).filter(User.user_id == booking.user_id).first()
                    user_name = user.username if user else "Неизвестно"
                    label = f"Клиент: {user_name}"
                else:
                    # Для пользователя показываем имя мастера
                    master = session.query(Master).filter(Master.master_id == booking.master_id).first()
                    master_name = master.master_name if master else "Неизвестно"
                    label = f"Мастер: {master_name}"

                buttons.append(
                    [InlineKeyboardButton(
                        text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {label}",
                        callback_data=f"view_active_booking_{booking.booking_id}"
                    )]
                )

            # Добавляем кнопку "Назад"
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            # Отправляем сообщение с кнопками
            await callback_query.message.edit_text(
                "Ваши активные записи:",
                reply_markup=markup
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке активных записей: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке активных записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()  # В случае ошибки, возвращаем в меню с записями
        )


@router_bookings.callback_query(lambda c: c.data == "booking_history")
async def process_user_history(callback_query: CallbackQuery):
    """Обработчик для кнопки 'История записей' у пользователя."""
    user_id = callback_query.from_user.id  # Получаем ID пользователя
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            # Проверяем, является ли пользователь мастером, путем поиска в таблице мастеров
            is_master = session.query(Master).filter(Master.master_id == user_id).first()

            if is_master:  # Если пользователь — мастер, показываем историю для мастера
                master_id = user_id
                logger.debug(f"Пользователь с ID {user_id} является мастером. Запрос истории для мастера.")

                # Получаем записи для мастера
                user_history_bookings = session.query(Booking).filter(
                    Booking.master_id == master_id,  # Фильтруем по master_id
                    (Booking.booking_datetime < current_time) |  # Прошедшие записи
                    (Booking.status == "cancelled")  # Отменённые записи
                ).order_by(Booking.booking_datetime.desc()).all()

            else:  # Если пользователь не мастер, показываем его собственную историю
                logger.debug(f"Пользователь с ID {user_id} не является мастером. Запрос истории для пользователя.")

                # Получаем записи для пользователя
                user_history_bookings = session.query(Booking).filter(
                    Booking.user_id == user_id,  # Фильтруем по user_id
                    (Booking.booking_datetime < current_time) |  # Прошедшие записи
                    (Booking.status == "cancelled")  # Отменённые записи
                ).order_by(Booking.booking_datetime.desc()).all()

            logger.debug(
                f"Запрос истории для пользователя {user_id}. Количество найденных записей: {len(user_history_bookings)}")

            if not user_history_bookings:
                await callback_query.message.edit_text(
                    "У вас ещё нет ни одной записи. Как только они появятся, вы сможете посмотреть их здесь.",
                    reply_markup=back_to_my_bookings_menu()  # Синхронный вызов
                )
                return

            buttons = []
            for booking in user_history_bookings:
                if is_master:  # Если мастер, выводим пользователя, который сделал запись
                    user_name = session.query(User.username).filter(User.user_id == booking.user_id).first()
                    user_name = user_name[0] if user_name else "Неизвестно"
                    label = f"Пользователь: {user_name}"
                else:  # Если обычный пользователь, показываем мастера
                    master_name = session.query(Master.master_name).filter(
                        Master.master_id == booking.master_id).first()
                    master_name = master_name[0] if master_name else "Неизвестно"
                    label = f"Мастер: {master_name}"

                # Проверяем статус записи
                if booking.status == "cancelled":
                    status = "Отменена"
                elif booking.booking_datetime < current_time:
                    status = "Прошедшая"
                else:
                    status = "Неизвестный статус"

                logger.debug(
                    f"Запись: ID={booking.booking_id}, Статус={status}, {label}, Дата={booking.booking_datetime}")

                # Создаем кнопку для каждой записи
                buttons.append(
                    [InlineKeyboardButton(
                        text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {status} - {label}",
                        callback_data="ignore"  # Плейсхолдер для кнопки
                    )]
                )

            buttons.append([InlineKeyboardButton(text="Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("Ваша история записей:", reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()  # Синхронный вызов
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()  # Синхронный вызов
        )


@router_bookings.callback_query(lambda c: c.data.startswith("view_active_booking_"))
async def process_view_active_booking(callback_query: CallbackQuery):
    """Обработчик для кнопки просмотра активной записи."""
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            # Получаем имя мастера
            master_name = session.query(Master.master_name).filter(Master.master_id == booking.master_id).first()
            master_name = master_name[0] if master_name else "Неизвестно"

            # Формируем кнопки для отмены или возврата
            buttons = [
                [InlineKeyboardButton(text="Отменить", callback_data=f"cancel_booking_{booking.booking_id}")],
                [InlineKeyboardButton(text="Назад", callback_data="active_bookings")]
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            # Отправляем сообщение с информацией о записи
            await callback_query.message.edit_text(
                f"Запись: {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')}\nМастер: {master_name}",
                reply_markup=markup
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )


@router_bookings.callback_query(lambda c: c.data.startswith("cancel_booking_"))
async def process_cancel_booking(callback_query: CallbackQuery):
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            # Получение записи по ID
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            if booking.status == "cancelled":
                await callback_query.message.edit_text("Эта запись уже отменена.",
                                                       reply_markup=back_to_my_bookings_menu())
                return

            # Обновляем статус записи на "cancelled"
            session.execute(
                Booking.__table__.update().where(Booking.booking_id == booking_id).values(status="cancelled")
            )
            session.commit()

            logger.debug(f"Запись ID {booking.booking_id} успешно отменена.")

            master_id = booking.master_id
            booking_date = booking.booking_datetime.date()

            start_time = 10
            end_time = 22
            time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]

            active_bookings = session.query(Booking).filter(
                Booking.master_id == master_id,
                func.date(Booking.booking_datetime) == booking_date,
                Booking.status != "cancelled"
            ).all()

            blocked_times = set()
            for active_booking in active_bookings:
                booked_hour_int = active_booking.booking_datetime.hour
                for i in range(0, 3):
                    blocked_hour = booked_hour_int + i
                    if start_time <= blocked_hour <= end_time:
                        blocked_times.add(f"{blocked_hour:02}:00")

            time_buttons = []
            for time in time_slots:
                if time in blocked_times:
                    time_buttons.append([InlineKeyboardButton(text=f"❌ {time}", callback_data="ignore")])
                else:
                    time_buttons.append(
                        [InlineKeyboardButton(text=time,
                                              callback_data=f"time_{master_id}_{booking_date.strftime('%d.%m.%Y')}_{time}:00")]
                    )

            time_buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"master_{master_id}")])

            await callback_query.message.edit_text(
                "Обновленный список доступного времени:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=time_buttons)
            )
            logger.debug("Временные слоты успешно освобождены и обновлены.")

            await callback_query.answer("Запись успешно отменена.", show_alert=True)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )


def back_to_my_bookings_menu():
    """Кнопка возврата в меню 'Мои записи'."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="my_bookings")]
    ])
