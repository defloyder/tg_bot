import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master  # Модели таблицы записей и мастеров
from database.database import SessionFactory
from menu import my_bookings_menu

# Создаём логгер для отладки
logger = logging.getLogger(__name__)

router_bookings = Router(name="bookings")


@router_bookings.callback_query(lambda c: c.data == "my_bookings")
async def process_my_bookings(callback_query: CallbackQuery):
    """Обработчик для кнопки 'Мои записи'."""
    await callback_query.answer()
    await callback_query.message.edit_text("Выберите опцию:", reply_markup=my_bookings_menu())


@router_bookings.callback_query(lambda c: c.data == "process_active_bookings")
async def process_active_bookings(callback_query: CallbackQuery):
    """Обработчик для отображения активных записей."""
    try:
        user_id = callback_query.from_user.id
        with SessionFactory() as session:
            active_bookings = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Master.master_name
            ).join(Master, Master.master_id == Booking.master_id).filter(
                Booking.user_id == user_id,
                Booking.status == None,  # Статус "null" обозначает активную запись
                Booking.booking_datetime > datetime.now()  # Запись не должна быть в прошлом
            ).all()

            if not active_bookings:
                await callback_query.message.edit_text(
                    "У вас нет активных записей.",
                    reply_markup=back_to_my_bookings_menu()
                )
                return

            buttons = [
                [InlineKeyboardButton(
                    text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {booking.master_name}",
                    callback_data=f"view_active_booking_{booking.booking_id}"
                )]
                for booking in active_bookings
            ]

            # Добавляем кнопку "Назад"
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text(
                "Ваши активные записи:",
                reply_markup=markup
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке активных записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке активных записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )


@router_bookings.callback_query(lambda c: c.data == "booking_history")
async def process_user_history(callback_query: CallbackQuery):
    """Обработчик для кнопки 'История записей' у пользователя."""
    user_id = callback_query.from_user.id
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            user_history_bookings = session.query(Booking).filter(
                Booking.user_id == user_id,
                (Booking.booking_datetime < current_time) |  # Прошедшие записи
                (Booking.status == "cancelled")  # Отменённые записи
            ).order_by(Booking.booking_datetime.desc()).all()

            logger.debug(
                f"Запрос истории для пользователя {user_id}. Количество найденных записей: {len(user_history_bookings)}")

            if not user_history_bookings:
                await callback_query.message.edit_text(
                    "У вас ещё нет ни одной записи. Как только они появятся, вы сможете посмотреть их здесь.",
                    reply_markup=back_to_my_bookings_menu()
                )
                return

            buttons = []
            for booking in user_history_bookings:
                master_name = session.query(Master.master_name).filter(Master.master_id == booking.master_id).first()
                master_name = master_name[0] if master_name else "Неизвестно"

                status = (
                    "Отменена" if booking.status == "cancelled" else
                    "Прошедшая" if booking.booking_datetime < current_time else
                    "Активная"
                )

                logger.debug(
                    f"Запись: ID={booking.booking_id}, Статус={status}, Мастер={master_name}, Дата={booking.booking_datetime}")

                buttons.append(
                    [InlineKeyboardButton(
                        text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {status} - Мастер: {master_name}",
                        callback_data="ignore"  # Добавляем placeholder, чтобы Telegram принял кнопку
                    )]
                )

            buttons.append([InlineKeyboardButton(text="Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("Ваша история записей:", reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu()
        )


@router_bookings.callback_query(lambda c: c.data.startswith("view_active_booking_"))
async def process_view_active_booking(callback_query: CallbackQuery):
    """Обработчик для кнопки просмотра активной записи."""
    booking_id = int(callback_query.data.split("_")[-1])  # Пытаемся извлечь ID записи

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
                [InlineKeyboardButton(text="Назад", callback_data="process_active_bookings")]
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
    """Обработчик для отмены записи."""
    booking_id = int(callback_query.data.split("_")[-1])  # Извлекаем ID записи

    try:
        with SessionFactory() as session:
            # Пытаемся найти запись по ID
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            # Проверяем, что запись еще активна (статус не 'cancelled')
            if booking.status == "cancelled":
                await callback_query.message.edit_text("Эта запись уже отменена.",
                                                       reply_markup=back_to_my_bookings_menu())
                return

            # Логируем данные записи перед отменой
            logger.debug(f"Запись до отмены: {booking}")

            # Обновляем статус записи на 'cancelled' без обращения напрямую к объекту
            session.execute(
                Booking.__table__.update().where(Booking.booking_id == booking_id).values(status="cancelled")
            )
            session.commit()  # Сохраняем изменения в базе данных

            # Проверяем занятость всех слотов мастера на указанную дату
            master_id = booking.master_id
            booking_datetime = booking.booking_datetime
            booking_date = booking_datetime.date()

            booked_slots = session.query(Booking).filter(
                Booking.master_id == master_id,
                Booking.booking_datetime.date() == booking_date,
                Booking.status != "cancelled"  # Игнорируем отменённые записи
            ).all()

            is_slot_freed = all(booking.booking_datetime != booking_datetime for booking in booked_slots)

            if is_slot_freed:
                logger.debug(f"Время {booking_datetime.time()} на {booking_date} для мастера {master_id} теперь свободно.")
                # Здесь можно дополнительно уведомить пользователя или обновить интерфейс для новых записей.

            # Отправляем подтверждение пользователю
            await callback_query.message.edit_text(f"Запись ID {booking.booking_id} успешно отменена.",
                                                   reply_markup=back_to_my_bookings_menu())

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
