from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master, User
from database.database import SessionFactory
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

# Обработчик для кнопки "windows" - Окошки мастера (можно добавить функциональность для окон)
@router_master_admin.callback_query(lambda c: c.data == "windows")
async def windows(c: CallbackQuery):
    """Обработчик для отображения информации об окошках мастера."""
    try:
        # Здесь может быть любая логика для окна мастера
        markup = await main_menu(c.from_user.id)  # Получаем клавиатуру
        await c.message.edit_text("Информация о ваших окошках. (Здесь можно добавить логику для работы с окнами)", reply_markup=markup)
    except Exception as e:
        markup = await main_menu(c.from_user.id)  # Получаем клавиатуру
        await c.message.edit_text(f"Произошла ошибка: {str(e)}", reply_markup=markup)
