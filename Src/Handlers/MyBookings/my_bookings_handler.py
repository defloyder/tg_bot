import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master, User
from database.database import SessionFactory
from menu import my_bookings_menu

logger = logging.getLogger(__name__)

router_bookings = Router(name="bookings")


@router_bookings.callback_query(lambda c: c.data == "my_bookings")
async def process_my_bookings(callback_query: CallbackQuery):
    """Обработчик для кнопки 'Мои записи'."""
    await callback_query.answer()
    await callback_query.message.edit_text(
        "<b>Выберите опцию:</b>",
        reply_markup=my_bookings_menu(),
        parse_mode="HTML"
    )


@router_bookings.callback_query(lambda c: c.data == "active_bookings")
async def process_active_bookings(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            is_master = session.query(Master).filter(Master.master_id == user_id).first()

            if is_master:
                active_bookings = session.query(Booking).filter(
                    Booking.master_id == user_id,
                    Booking.status == 'new',
                    Booking.booking_datetime > current_time
                ).order_by(Booking.booking_datetime).all()
            else:
                active_bookings = session.query(Booking).filter(
                    Booking.user_id == user_id,
                    Booking.status == 'new',
                    Booking.booking_datetime > current_time
                ).order_by(Booking.booking_datetime).all()

            if not active_bookings:
                await callback_query.message.edit_text(
                    "ℹ <b>У вас нет активных записей.</b>",
                    reply_markup=back_to_my_bookings_menu(),
                    parse_mode="HTML"
                )
                return

            buttons = []
            for booking in active_bookings:
                booking_date = booking.booking_datetime.strftime('%d.%m.%Y')
                booking_time = booking.booking_datetime.strftime('%H:%M')

                if is_master:
                    user = session.query(User).filter(User.user_id == booking.user_id).first()
                    user_name = user.username if user else "<i>Неизвестно</i>"
                    label = f"👤 Клиент: {user_name}"
                else:
                    master = session.query(Master).filter(Master.master_id == booking.master_id).first()
                    master_name = master.master_name if master else "<i>Неизвестно</i>"
                    label = f"⚜️ Мастер: {master_name}"

                buttons.append([
                    InlineKeyboardButton(
                        text=f"📅 {booking_date} ⏰ {booking_time} - {label}",
                        callback_data=f"view_active_booking_{booking.booking_id}"
                    )
                ])

            buttons.append([InlineKeyboardButton(text="⬅ Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text(
                "<b>Ваши активные записи:</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Ошибка при обработке активных записей: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при загрузке активных записей</b>. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu(),
            parse_mode="HTML"
        )


@router_bookings.callback_query(lambda c: c.data == "booking_history")
async def process_user_history(callback_query: CallbackQuery):
    """Обработчик для кнопки 'История записей'."""
    user_id = callback_query.from_user.id
    current_time = datetime.now()

    try:
        with SessionFactory() as session:
            is_master = session.query(Master).filter(Master.master_id == user_id).first()

            if is_master:
                user_history_bookings = session.query(Booking).filter(
                    Booking.master_id == user_id,
                    (Booking.booking_datetime < current_time) |
                    (Booking.status == "cancelled")
                ).order_by(Booking.booking_datetime.desc()).all()
            else:
                user_history_bookings = session.query(Booking).filter(
                    Booking.user_id == user_id,
                    (Booking.booking_datetime < current_time) |
                    (Booking.status == "cancelled")
                ).order_by(Booking.booking_datetime.desc()).all()

            if not user_history_bookings:
                await callback_query.message.edit_text(
                    "ℹ <b>У вас ещё нет ни одной записи.</b> Как только они появятся, вы сможете посмотреть их здесь.",
                    reply_markup=back_to_my_bookings_menu(),
                    parse_mode="HTML"
                )
                return

            buttons = []
            for booking in user_history_bookings:
                booking_date = booking.booking_datetime.strftime('%d.%m.%Y')
                booking_time = booking.booking_datetime.strftime('%H:%M')

                if is_master:
                    user = session.query(User).filter(User.user_id == booking.user_id).first()
                    user_name = user.username if user else "<i>Неизвестно</i>"
                    label = f"👤 Клиент: {user_name}"
                else:
                    master = session.query(Master).filter(Master.master_id == booking.master_id).first()
                    master_name = master.master_name if master else "<i>Неизвестно</i>"
                    label = f"⚜️ Мастер: {master_name}"

                status = "❌ Отменена" if booking.status == "cancelled" else "✅ Прошедшая"

                buttons.append([
                    InlineKeyboardButton(
                        text=f"📅 {booking_date} ⏰ {booking_time} - {status} - {label}",
                        callback_data="ignore"
                    )
                ])

            buttons.append([InlineKeyboardButton(text="⬅ Назад", callback_data="my_bookings")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text(
                "<b>История записей:</b>",
                reply_markup=markup,
                parse_mode="HTML"
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при загрузке вашей истории записей</b>. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при загрузке вашей истории записей</b>. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu(),
            parse_mode="HTML"
        )


@router_bookings.callback_query(lambda c: c.data.startswith("view_active_booking_"))
async def process_view_active_booking(callback_query: CallbackQuery):
    """Обработчик для кнопки просмотра активной записи."""
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("❌ <b>Запись не найдена</b>.",
                                                       reply_markup=back_to_my_bookings_menu(),
                                                       parse_mode="HTML")
                return

            is_master = session.query(Master).filter(Master.master_id == callback_query.from_user.id).first()

            master = session.query(Master).filter(Master.master_id == booking.master_id).first()
            master_name = master.master_name if master else "<i>Неизвестно</i>"

            user = session.query(User).filter(User.user_id == booking.user_id).first()
            user_display_name = user.username if user and user.username else "<i>Неизвестный пользователь</i>"

            booking_date = booking.booking_datetime.strftime('%d.%m.%Y')
            booking_time = booking.booking_datetime.strftime('%H:%M')

            if is_master:
                details = (
                    f"<b>📅 Дата:</b> {booking_date}\n"
                    f"<b>⏰ Время:</b> {booking_time}\n"
                    f"<b>👤 Клиент:</b> {user_display_name}\n"
                    f"<b>🔗 ID клиента:</b> <a href='tg://user?id={booking.user_id}'>{booking.user_id}</a>\n"
                )
            else:
                details = (
                    f"<b>📅 Дата:</b> {booking_date}\n"
                    f"<b>⏰ Время:</b> {booking_time}\n"
                    f"<b>⚜️ Мастер:</b> {master_name}\n"
                    f"⛩️<b> Адрес:</b> г. Москва, метро Владыкино, ул. Ботаническая 14а\n"

                )

            buttons = [
                [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel_booking_{booking.booking_id}")],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="active_bookings")]
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text(details, reply_markup=markup, parse_mode="HTML")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при загрузке информации о записи</b>. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await callback_query.message.edit_text(
            "❌ <b>Произошла ошибка при загрузке информации о записи</b>. Попробуйте позже.",
            reply_markup=back_to_my_bookings_menu(),
            parse_mode="HTML"
        )


@router_bookings.callback_query(lambda c: c.data.startswith("cancel_booking_"))
async def process_cancel_booking(callback_query: CallbackQuery):
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            if booking.status == "cancelled":
                await callback_query.message.edit_text("Эта запись уже отменена.",
                                                       reply_markup=back_to_my_bookings_menu())
                return

            session.execute(
                Booking.__table__.update().where(Booking.booking_id == booking_id).values(status="cancelled")
            )
            session.commit()

            logger.debug(f"Запись ID {booking.booking_id} успешно отменена.")

            if booking.user_id:
                try:
                    await callback_query.bot.send_message(
                        booking.user_id,
                        f"🔔 Ваша запись на {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена мастером.",
                    )
                    logger.info(f"✅ Уведомление отправлено пользователю {booking.user_id}.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю {booking.user_id}: {e}")

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
        [InlineKeyboardButton(text="⬅ Назад", callback_data="my_bookings")]
    ])
