import os
from datetime import datetime
from tempfile import NamedTemporaryFile
from typing import Union

import aiogram
import pandas as pd
from aiogram import Router
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
from aiogram.types import Message
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from sqlalchemy import Date
from sqlalchemy.exc import SQLAlchemyError

from Src.Handlers.Booking.service import generate_calendar
from database import Booking, Master
from database.database import SessionFactory
from database.models import PriceList, User
from logger_config import logger
from menu import admin_panel, main_menu

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

    # Удаляем сообщение с прайсом, если оно существует
    global price_message_id
    if price_message_id:
        try:
            await callback_query.message.bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=price_message_id
            )
            price_message_id = None  # Сбрасываем id сообщения после удаления
        except aiogram.exceptions.TelegramBadRequest as e:
            logger.error(f"Ошибка при удалении сообщения с прайсом: {e}")
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с прайсом: {e}")

    # Проверяем, существует ли сообщение, перед тем как редактировать
    if callback_query.message:
        try:
            # Получаем меню для пользователя
            reply_markup = await main_menu(user_id)

            # Редактируем сообщение с новым текстом и клавиатурой
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
                    "ID пользователя": int(booking.user_id),  # Преобразование в числовой формат
                    "Имя мастера": booking.master_name,
                    "Статус": booking.status or "Не указано"  # Обработка пустых статусов
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
                col_letter = column_cells[0].column_letter  # Определяем букву колонки
                for cell in column_cells:
                    if cell.value:
                        cell.alignment = Alignment(wrap_text=True)  # Включаем перенос текста
                        max_length = max(max_length, len(str(cell.value)))
                ws.column_dimensions[col_letter].width = max_length + 2  # Увеличиваем ширину

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
                    "❌ Запись не найдена. Возможно, она была удалена.",
                    reply_markup=admin_panel()
                )
                return

            # Определяем статус записи
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

            # Получаем имя пользователя, связанного с записью
            if booking.user_id:
                user = session.query(User).filter(User.user_id == booking.user_id).first()
                if user:
                    if user.username:  # Если есть username
                        user_display_name = f"@{user.username}"
                    elif user.full_name:  # Если есть полное имя
                        user_display_name = user.full_name
                    else:  # Если ни username, ни имени нет
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

            # Определяем, какие кнопки показывать в зависимости от статуса
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

            # Обновляем статус записи
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


@router_admin.callback_query(lambda c: c.data == "edit_price_list")
async def edit_price_list_start(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.edit_text("📝 Введите описание для прайс-листа:")
    await state.set_state(PriceListState.waiting_for_description)


@router_admin.message(PriceListState.waiting_for_description)
async def process_price_list_description(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, отправьте текстовое описание для прайс-листа.")
        return

    await state.update_data(description=message.text)
    await message.answer("📸 Теперь отправьте фотографию для прайс-листа:")
    await state.set_state(PriceListState.waiting_for_photo)


@router_admin.message(PriceListState.waiting_for_photo)
async def process_price_list_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    description = data.get("description")

    if not message.photo:
        await message.answer("❗ Пожалуйста, отправьте фотографию для прайс-листа.")
        return

    photo = message.photo[-1]
    file_id = photo.file_id

    try:
        file = await message.bot.get_file(file_id)
        os.makedirs("photos", exist_ok=True)
        extension = file.file_path.split('.')[-1]
        price_photo = f"photos/price_list_{file.file_id}.{extension}"
        await message.bot.download_file(file.file_path, destination=price_photo)

        with SessionFactory() as session:
            price_list = session.query(PriceList).first()
            if price_list:
                price_list.price_description = description
                price_list.price_photo = price_photo
            else:
                price_list = PriceList(price_description=description, price_photo=price_photo)
                session.add(price_list)
            session.commit()

        if price_message_id:
            await message.bot.edit_message_media(
                media=types.InputMediaPhoto(price_photo, caption=description),
                chat_id=message.chat.id,
                message_id=price_message_id
            )
            await message.answer("✅ Прайс-лист успешно обновлён!")
        else:
            await message.answer("✅ Прайс-лист успешно обновлён, но ещё не был отображен.")

    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении прайс-листа: {e}")
        await message.answer("⚠️ Произошла ошибка при обновлении прайс-листа.")
    finally:
        await state.clear()


@router_admin.callback_query(lambda c: c.data == "get_price_list")
async def show_price_list(callback_query: CallbackQuery, state: FSMContext):
    global price_message_id
    try:
        if price_message_id:
            await callback_query.answer()

        with SessionFactory() as session:
            price_list = session.query(PriceList).first()

        if price_list:
            description = price_list.price_description
            price_photo = price_list.price_photo
            logger.debug(f"Прайс-лист найден. Описание: {description}, Фото: {price_photo}")

            back_button = InlineKeyboardButton(text=f"⬅️ Назад", callback_data="main_menu")
            buttons = [[back_button]]
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            if os.path.exists(price_photo):
                input_file = FSInputFile(price_photo, filename=os.path.basename(price_photo))

                if price_message_id:
                    await callback_query.message.bot.edit_message_media(
                        media=types.InputMediaPhoto(input_file, caption=f"📋 Прайс-лист: {description}"),
                        chat_id=callback_query.message.chat.id,
                        message_id=price_message_id,
                        reply_markup=markup
                    )
                else:
                    price_message = await callback_query.message.bot.send_photo(
                        callback_query.message.chat.id,
                        input_file,
                        caption=f"📋: {description}",
                        reply_markup=markup
                    )
                    price_message_id = price_message.message_id
            else:
                if price_message_id:
                    await callback_query.message.bot.edit_message_text(
                        text=f"📋: {description}",
                        chat_id=callback_query.message.chat.id,
                        message_id=price_message_id,
                        reply_markup=markup
                    )
                else:
                    await callback_query.message.bot.send_message(
                        callback_query.message.chat.id,
                        text=f"📋 Прайс-лист: {description}",
                        reply_markup=markup
                    )
        else:
            await callback_query.message.edit_text(
                "⚠️ Прайс-лист не найден.",
                reply_markup=admin_panel()
            )

    except Exception as e:
        logger.error(f"Ошибка при получении прайс-листа: {e}")
        await callback_query.message.edit_text(
            "⚠️ Произошла ошибка при загрузке прайс-листа. Попробуйте позже.",
            reply_markup=admin_panel()
        )

@router_admin.message(lambda message: isinstance(message.text, str) and message.text.lower() == 'get_price_list')
async def callback_get_price_list(callback_query: CallbackQuery, state: FSMContext):
    # Проверка текущего состояния FSM
    current_state = await state.get_state()
    logger.debug(f"Current FSM state: {current_state}")
    await show_price_list(callback_query.message)


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