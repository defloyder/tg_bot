from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, User
from database.database import SessionFactory
from logger_config import logger
from menu import main_menu, back_to_master_menu

router_master_admin = Router(name="master_admin")


@router_master_admin.callback_query(lambda c: c.data == "main_menu")
async def back_to_main(c: CallbackQuery):
    """Обработчик для возвращения в главное меню"""
    markup = await main_menu(c.from_user.id)
    await c.message.edit_text("Вы вернулись в главное меню.", reply_markup=markup)


@router_master_admin.callback_query(lambda c: c.data == "active_bookings")
async def active_bookings(c: CallbackQuery):
    """Обработчик для отображения активных записей мастера."""
    master_id = c.from_user.id
    try:
        with SessionFactory() as session:
            active_bookings = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id
            ).filter(
                Booking.master_id == master_id,
                Booking.status == None,
                Booking.booking_datetime > datetime.now()
            ).all()

            if not active_bookings:
                markup = await main_menu(c.from_user.id)
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
        markup = await main_menu(c.from_user.id)
        await c.message.edit_text(f"Произошла ошибка: {str(e)}", reply_markup=markup)


@router_master_admin.callback_query(lambda c: c.data == "booking_history")
async def process_master_history(callback_query: CallbackQuery):
    """Обработчик для кнопки 'История записей' у мастера."""
    master_id = callback_query.from_user.id
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            master_history_bookings = session.query(Booking).filter(
                Booking.master_id == master_id,
                (Booking.booking_datetime < current_time) |
                (Booking.status == "cancelled")
            ).order_by(Booking.booking_datetime.desc()).all()

            logger.debug(
                f"Запрос истории для мастера {master_id}. Количество найденных записей: {len(master_history_bookings)}")

            if not master_history_bookings:
                await callback_query.message.edit_text(
                    "У вас нет прошедших или отменённых записей.",
                    reply_markup=back_to_master_menu()
                )
                return

            buttons = []
            for booking in master_history_bookings:
                user = session.query(User).filter(User.user_id == booking.user_id).first()
                user_name = user.full_name if user else "Неизвестно"

                if booking.status == "cancelled":
                    status = "Отменена"
                elif booking.booking_datetime < current_time:
                    status = "Прошедшая"
                else:
                    status = "Неизвестный статус"

                logger.debug(
                    f"Запись: ID={booking.booking_id}, Статус={status}, Клиент={user_name}, Дата={booking.booking_datetime}")

                buttons.append(
                    [InlineKeyboardButton(
                        text=f"{booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} - {status} - Клиент: {user_name}",
                        callback_data="ignore"
                    )]
                )

            buttons.append([InlineKeyboardButton(text="Назад", callback_data="master_menu")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("Ваша история записей:", reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_master_menu()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке вашей истории записей. Попробуйте позже.",
            reply_markup=back_to_master_menu()
        )


@router_master_admin.callback_query(lambda c: c.data == "windows")
async def windows(c: CallbackQuery):
    """Меню управления расписанием."""
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Управление расписанием", callback_data="manage_schedule")],
            [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
        ]
    )
    await c.message.edit_text("Выберите действие:", reply_markup=markup)
