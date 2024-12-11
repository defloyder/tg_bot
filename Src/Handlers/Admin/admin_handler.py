from datetime import datetime
from datetime import datetime
from tempfile import NamedTemporaryFile

import aiogram
import pandas as pd
from aiogram import Router
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from sqlalchemy.exc import SQLAlchemyError

from Src.Handlers.Booking.service import generate_calendar
from database import Booking, Master
from database.database import SessionFactory
from database.models import User
from logger_config import logger
from menu import admin_panel, main_menu, price_list_settings_menu

router_admin = Router(name="admin")

ADMIN_ID = [475953677, 962757762]


class PriceListState(StatesGroup):
    waiting_for_description = State()
    waiting_for_photo = State()


price_message_id = None


@router_admin.callback_query(lambda c: c.data == "admin_panel")
async def process_callback_admin_panel(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in ADMIN_ID:
        await callback_query.answer()
        await callback_query.message.edit_text("🛠️ Административная панель:", reply_markup=admin_panel())
        logger.info(f"Администратор {user_id} открыл административную панель.")
    else:
        await callback_query.answer("🚫 У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} попытался открыть административную панель.")


@router_admin.callback_query(lambda c: c.data == "main_menu")
async def main_menu_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    global price_message_id
    if price_message_id:
        try:
            await callback_query.message.bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=price_message_id
            )
            price_message_id = None
        except aiogram.exceptions.TelegramBadRequest as e:
            logger.error(f"Ошибка при удалении сообщения с прайсом: {e}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с прайсом: {e}")

    if callback_query.message:
        try:
            reply_markup = await main_menu(user_id)

            await callback_query.message.edit_text(
                "🏠 Вы в главном меню. Выберите нужную опцию.",
                reply_markup=reply_markup
            )
        except aiogram.exceptions.TelegramBadRequest as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
        except Exception as e:
            logger.error(f"Не удалось отредактировать сообщение: {e}")
    else:
        logger.error(f"Сообщение для редактирования не найдено.")

    logger.info(f"Пользователь {user_id} вернулся в главное меню.")


@router_admin.callback_query(lambda c: c.data == "all_booking_history")
async def process_all_booking_history(callback_query: CallbackQuery):
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
                    "📅 В базе данных нет записей.",
                    reply_markup=admin_panel()
                )
                return

            sorted_bookings = sorted(all_bookings, key=lambda x: (
                x.status == "active",
                x.booking_datetime < datetime.now(),
                x.status == "cancelled"
            ))

            buttons = []
            for booking in sorted_bookings:
                status = (
                    "❌ Отменена" if booking.status == "cancelled" else
                    "🟠 Прошедшая" if booking.booking_datetime < datetime.now() else
                    "🟢 Активная"
                )

                cancel_button = None
                if booking.status == "active" and booking.booking_datetime > datetime.now():
                    cancel_button = InlineKeyboardButton(
                        text="❌ Отменить запись", callback_data=f"cancel_booking_{booking.booking_id}"
                    )

                button_row = [
                    InlineKeyboardButton(
                        text=f"{status} | {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} "
                             f"| Мастер: {booking.master_name} | Пользователь: {booking.user_id} | {booking.booking_id}",
                        callback_data=f"view_booking_{booking.booking_id}"
                    )
                ]

                if cancel_button:
                    button_row.append(cancel_button)
                buttons.append(button_row)

            buttons.append(
                [InlineKeyboardButton(text="📊 Экспортировать в Excel", callback_data="export_bookings_to_excel")])
            buttons.append([InlineKeyboardButton(text="🗑️ Удалить все записи", callback_data="delete_all_bookings")])
            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("📜 История всех записей (нажмите для подробностей):",
                                                   reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при загрузке всех записей: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке всех записей: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data == "delete_all_bookings")
async def delete_all_bookings(callback_query: CallbackQuery):
    """Обработчик для удаления всех записей из базы данных и списка."""
    try:
        with SessionFactory() as session:
            session.query(Booking).delete()
            session.commit()

            await callback_query.message.edit_text(
                "🧹 Все записи были удалены.",
                reply_markup=admin_panel()
            )
            logger.info("Все записи были удалены администратором.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при удалении всех записей: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при удалении всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при удалении всех записей: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при удалении всех записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data == "export_bookings_to_excel")
async def export_bookings_to_excel(callback_query: CallbackQuery):
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
                await callback_query.answer("⚠️ Нет записей для экспорта.", show_alert=True)
                return

            data = [
                {
                    "ID записи": booking.booking_id,
                    "Дата и время": booking.booking_datetime.strftime('%d.%m.%Y %H:%M'),
                    "ID пользователя": int(booking.user_id),
                    "Имя мастера": booking.master_name,
                    "Статус": booking.status or "Не указано"
                }
                for booking in all_bookings
            ]

            df = pd.DataFrame(data)

            now = datetime.now().strftime('%Y-%m-%d_%H-%M')
            file_name = f"История_записей_{now}.xlsx"

            with NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
                file_path = temp_file.name
                df.to_excel(file_path, index=False)

            wb = load_workbook(file_path)
            ws = wb.active

            for column_cells in ws.columns:
                max_length = 0
                col_letter = column_cells[0].column_letter
                for cell in column_cells:
                    if cell.value:
                        cell.alignment = Alignment(wrap_text=True)
                        max_length = max(max_length, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max_length + 2

            wb.save(file_path)
            wb.close()
            file = FSInputFile(file_path, filename=file_name)
            await callback_query.message.answer_document(
                file,
                caption=f"Экспорт истории записей выполнен: {file_name}"
            )
    except Exception as e:
        logger.error(f"⚠️ Ошибка при экспорте записей в Excel: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при экспорте записей. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data.startswith("view_booking_"))
async def view_booking_details(callback_query: CallbackQuery):
    """Обработчик для просмотра подробной информации о записи."""
    booking_id = int(callback_query.data.split("_")[-1])  # Извлекаем ID записи

    try:
        with SessionFactory() as session:
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
                    "❌ Запись не найдена. Возможно, она была удалена.",
                    reply_markup=admin_panel()
                )
                return

            status = (
                "⛔ Отменена" if booking.status == "cancelled" else
                "🟠 Прошедшая" if booking.booking_datetime < datetime.now() else
                "🟢 Активная"
            )

            details = (
                f"🆔 ID записи: {booking.booking_id}\n"
                f"📅 Дата и время: {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"⚜️ Мастер: {booking.master_name}\n"
            )

            if booking.user_id:
                user = session.query(User).filter(User.user_id == booking.user_id).first()
                if user:
                    if user.username:
                        user_display_name = f"@{user.username}"
                    elif user.full_name:
                        user_display_name = user.full_name
                    else:
                        user_display_name = "Неизвестный пользователь"
                else:
                    user_display_name = "Неизвестный пользователь"
            else:
                user_display_name = "Неизвестный пользователь"

            details += (
                f"👤 Пользователь: {user_display_name}\n"
                f"💬 ID клиента: <a href='tg://user?id={booking.user_id}'>{booking.user_id}</a>\n"
                f"🔖 Статус: {status}\n"
            )

            logger.info(f"Детали записи: {details}")

            buttons = []
            if status == "🟢 Активная" and booking.booking_datetime > datetime.now():
                cancel_button = InlineKeyboardButton(
                    text="❌ Отменить запись", callback_data=f"cancel_booking_{booking.booking_id}"
                )
                buttons.append([cancel_button])

            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="all_booking_history")])

            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            await callback_query.message.edit_text(details, reply_markup=markup)

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при загрузке записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке информации о записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data.startswith("cancel_booking_"))
async def cancel_booking(callback_query: CallbackQuery):
    booking_id = int(callback_query.data.split("_")[-1])

    try:
        with SessionFactory() as session:
            booking = session.query(
                Booking.booking_id,
                Booking.booking_datetime,
                Booking.user_id,
                Master.master_name,
                Booking.status,
            ).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.answer("❌ Запись с таким ID не найдена.", show_alert=True)
                return

            if booking.status == "cancelled":
                await callback_query.answer("⚠️ Запись уже отменена.", show_alert=True)
                return

            session.execute(
                Booking.__table__.update().where(Booking.booking_id == booking_id).values(status="cancelled")
            )
            session.commit()

            logger.info(f"Запись с ID {booking_id} была отменена администратором.")

            if booking.user_id:
                try:
                    await callback_query.bot.send_message(
                        booking.user_id,
                        f"🔔 Ваша запись к мастеру {booking.master_name} на {booking.booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена администратором.",
                    )
                    logger.info(f"✅ Уведомление отправлено пользователю {booking.user_id}.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю {booking.user_id}: {e}")

            await callback_query.answer("✅ Запись успешно отменена.")
            await callback_query.message.edit_text(
                f"🔴 Запись с ID {booking_id} была успешно отменена.",
                reply_markup=admin_panel()
            )

    except SQLAlchemyError as e:
        logger.error(f"Ошибка SQLAlchemy при отмене записи {booking_id}: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при отмене записи. Попробуйте позже.",
            reply_markup=admin_panel()
        )


@router_admin.callback_query(lambda c: c.data == "price_list_settings")
async def handle_price_list_settings(callback_query: CallbackQuery):
    """Обработчик кнопки '⚙️ Настройка прайс-листов'."""
    await callback_query.message.edit_text(
        "Выберите действие с прайс-листом:",
        reply_markup=price_list_settings_menu()
    )


@router_admin.callback_query(lambda c: c.data.startswith("calendar_"))
async def handle_calendar_navigation(callback_query: CallbackQuery):
    """
    Обработчик навигации по календарю.
    """
    try:
        _, master_id, year, month = callback_query.data.split("_")
        year, month = int(year), int(month)

        markup = await generate_calendar(master_id, year, month)
        await callback_query.message.edit_reply_markup(reply_markup=markup)

    except Exception as e:
        logger.error(f"Ошибка обработки навигации по календарю: {e}")
        await callback_query.answer("Ошибка при обновлении календаря.", show_alert=True)
