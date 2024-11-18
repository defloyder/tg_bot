from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.exc import SQLAlchemyError

from database import Booking, Master
from database.database import SessionFactory
from logger_config import logger
from menu import admin_panel, back_to_main_menu, main_menu

router_admin = Router(name="admin")

ADMIN_ID = 475953677


@router_admin.callback_query(lambda c: c.data == "admin_panel")
async def process_callback_admin_panel(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        await callback_query.answer()
        await callback_query.message.edit_text("Административная панель:", reply_markup=admin_panel())
        logger.info(f"Администратор {user_id} открыл административную панель.")
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} попытался открыть административную панель.")


@router_admin.callback_query(lambda c: c.data == "main_menu")
async def main_menu_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id == ADMIN_ID:
        await callback_query.answer()
        await callback_query.message.edit_text(
            "Вы в главном меню. Выберите нужную опцию.", reply_markup=main_menu(user_id)
        )
        logger.info(f"Администратор {user_id} вернулся в главное меню.")
    else:
        await callback_query.message.edit_text(
            "Вы в главном меню. Выберите нужную опцию.", reply_markup=main_menu(user_id)
        )
        logger.info(f"Пользователь {user_id} вернулся в главное меню.")


@router_admin.callback_query(lambda c: c.data == "all_booking_history")
async def process_all_booking_history(callback_query: CallbackQuery):
    """Обработчик для отображения всей истории записей с сортировкой по статусу."""
    try:
        with SessionFactory() as session:
            all_bookings = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id,
                Master.master_name,
                Booking.status
            ).join(Master, Master.master_id == Booking.master_id).all()

            if not all_bookings:
                await callback_query.message.edit_text(
                    "В базе данных нет записей.",
                    reply_markup=admin_panel()
                )
                return

            # Сортируем записи: сначала прошедшие, потом активные, в конце отменённые
            sorted_bookings = sorted(all_bookings, key=lambda x: (
                x.status == "active",  # активные внизу
                x.booking_datetime < datetime.now(),  # прошедшие в середине
                x.status == "cancelled"  # отменённые в конце
            ))

            # Формируем кнопки для всех записей с краткой информацией
            buttons = []
            for booking in sorted_bookings:
                # Определяем статус
                status = (
                    "Отменена" if booking.status == "cancelled" else
                    "Прошедшая" if booking.booking_datetime < datetime.now() else
                    "Активная"
                )

                # Создание кнопки для отмены записи, если она активная
                cancel_button = None
                if booking.status == "active" and booking.booking_datetime > datetime.now():
                    cancel_button = InlineKeyboardButton(
                        text="Отменить запись", callback_data=f"cancel_booking_{booking.booking_id}"
                    )

                # Краткая информация
                button_row = [
                    InlineKeyboardButton(
                        text=f"{status} | {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} "
                             f"| Мастер: {booking.master_name} | Пользователь: {booking.user_id} | {booking.booking_id}",
                        callback_data=f"view_booking_{booking.booking_id}"  # Callback для подробного просмотра
                    )
                ]

                # Если кнопка отмены существует, добавляем ее
                if cancel_button:
                    button_row.append(cancel_button)

                # Добавляем кнопку в список
                buttons.append(button_row)

            # Добавляем кнопку для удаления всех записей
            buttons.append([InlineKeyboardButton(text="Удалить все записи", callback_data="delete_all_bookings")])

            # Добавляем кнопку "Назад"
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="admin_panel")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("История всех записей (нажмите для подробностей):", reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при загрузке всех записей: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке всех записей: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )

@router_admin.callback_query(lambda c: c.data == "delete_all_bookings")
async def delete_all_bookings(callback_query: CallbackQuery):
    """Обработчик для удаления всех записей из базы данных и списка."""
    try:
        with SessionFactory() as session:
            # Удаляем все записи из базы данных
            session.query(Booking).delete()
            session.commit()

            # Отправляем подтверждение
            await callback_query.message.edit_text(
                "Все записи были удалены.",
                reply_markup=admin_panel()
            )
            logger.info("Все записи были удалены администратором.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при удалении всех записей: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при удалении всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при удалении всех записей: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при удалении всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )

@router_admin.callback_query(lambda c: c.data.startswith("view_booking_"))
async def view_booking_details(callback_query: CallbackQuery):
    """Обработчик для просмотра подробной информации о записи."""
    booking_id = int(callback_query.data.split("_")[-1])  # Извлекаем ID записи

    try:
        with SessionFactory() as session:
            # Получаем запись по ID
            booking = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id,
                Master.master_name,
                Booking.status,
            ).join(Master, Master.master_id == Booking.master_id).filter(
                Booking.booking_id == booking_id
            ).first()

            if not booking:
                await callback_query.message.edit_text(
                    "Запись не найдена. Возможно, она была удалена.",
                    reply_markup=admin_panel()
                )
                return

            # Определяем статус
            status = (
                "Отменена" if booking.status == "cancelled" else
                "Прошедшая" if booking.booking_datetime < datetime.now() else
                "Активная"
            )

            # Полное описание записи
            details = (
                f"**ID записи:** {booking.booking_id}\n"
                f"**Дата и время:** {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"**Мастер:** {booking.master_name}\n"
                f"**Пользователь (ID):** {booking.user_id}\n"
                f"**Статус:** {status}\n"
            )


            # Создаем список кнопок
            buttons = []

            # Добавляем кнопку отмены, если запись активная и дата еще не прошла
            if status == "Активная" and booking.booking_datetime > datetime.now():
                cancel_button = InlineKeyboardButton(
                    text="Отменить запись", callback_data=f"cancel_booking_{booking.booking_id}"
                )
                buttons.append([cancel_button])  # Кнопка отмены добавляется в новый ряд

            # Кнопка "Назад"
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="all_booking_history")])

            # Создаем разметку
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            # Отображаем полную информацию
            await callback_query.message.edit_text(details, reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при загрузке записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data.startswith("cancel_booking_"))
async def cancel_booking(callback_query: CallbackQuery):
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.answer("Запись с таким ID не найдена.", show_alert=True)
                logger.error(f"Запись с ID {booking_id} не найдена для отмены.")
                return

            # Проверка на статус записи перед отменой
            if booking.status == "cancelled":
                await callback_query.answer("Запись уже отменена.", show_alert=True)
                return

            # Изменение статуса записи на отмененный
            booking.status = "cancelled"
            session.commit()

            await callback_query.answer("Запись успешно отменена.")
            await callback_query.message.edit_text(
                f"Запись с ID {booking_id} была успешно отменена.",
                reply_markup=admin_panel()
            )
            logger.info(f"Запись с ID {booking_id} была отменена.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )
