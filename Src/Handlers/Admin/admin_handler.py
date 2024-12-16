import calendar
from tempfile import NamedTemporaryFile
from datetime import datetime, time as datetime_time, timedelta

import aiogram
import pandas as pd
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import FSInputFile
from dateutil.relativedelta import relativedelta
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from sqlalchemy.exc import SQLAlchemyError

from Src.Handlers.Schedule.master_schedule_handler import toggle_day_block
from database import Booking, Master
from database.database import SessionFactory
from database.models import User, MasterSchedule, UserSchedule
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


@router_admin.callback_query(lambda c: c.data == "open_master_schedule_settings")
async def open_master_schedule_settings(callback_query: CallbackQuery):
    """
    Открывает меню выбора мастера для настройки расписания.
    """
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} открыл меню настройки мастеров.")

    # Проверка на админа
    if user_id not in ADMIN_ID:
        logger.warning(f"Пользователь {user_id} попытался получить доступ к настройкам мастеров без прав.")
        await callback_query.answer("🚫 У вас нет прав для доступа к этому меню.", show_alert=True)
        return

    try:
        # Получаем всех мастеров из базы данных
        with SessionFactory() as session:
            masters = session.query(Master).all()
        logger.info(f"Мастера загружены: {[master.master_id for master in masters]}")

        # Если мастера не найдены, сообщаем об этом
        if not masters:
            logger.info("Мастера не найдены.")
            await callback_query.message.edit_text("⚠️ Мастера не найдены.")
            return

        # Создаем клавиатуру для выбора мастера
        master_menu = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=f"👨‍🔧 {master.master_name}",
                                                   callback_data=f"edit_calendar_{master.master_id}")] for master in masters] +
                            [[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]]
        )

        # Отправляем сообщение с клавиатурой
        await callback_query.message.edit_text("Выберите мастера для настройки расписания:", reply_markup=master_menu)
    except Exception as e:
        logger.error(f"Ошибка при загрузке мастеров: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)



@router_admin.callback_query(lambda c: c.data.startswith("edit_calendar_"))
async def edit_master_calendar(callback_query: CallbackQuery, state: FSMContext):
    """
    Отображает календарь выбранного мастера для редактирования.
    """
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} открывает меню настройки расписания мастера.")

    if user_id not in ADMIN_ID:  # Проверяем, является ли пользователь админом
        logger.warning(f"Пользователь {user_id} попытался получить доступ к настройкам мастера без прав.")
        await callback_query.answer("🚫 У вас нет прав для доступа к этому меню.", show_alert=True)
        return

    try:
        master_id = int(callback_query.data.split("_")[2])  # Извлекаем ID мастера
        logger.info(f"Пользователь {user_id} выбрал мастера с ID {master_id}.")

        # Сохраняем master_id в состояние
        await state.update_data(master_id=master_id)
        logger.debug(f"master_id={master_id} сохранен в состоянии для пользователя {user_id}.")

        # Генерация календаря для выбранного мастера
        calendar_markup = await generate_schedule_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось загрузить календарь для мастера {master_id}.")
            await callback_query.message.edit_text("Не удалось загрузить календарь.", reply_markup=None)
            return

        # Отправляем календарь
        await callback_query.message.edit_text(
            "Настройте расписание мастера:",
            reply_markup=calendar_markup
        )
        logger.info(f"Календарь мастера {master_id} успешно открыт администратором {user_id}.")
    except Exception as e:
        logger.error(f"Ошибка при открытии календаря мастера: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@router_admin.callback_query(lambda c: c.data.startswith("toggle_block_"))
async def toggle_block(callback_query: CallbackQuery):
    """Обработчик для отображения временных слотов для выбранного дня."""
    try:
        user_id = callback_query.from_user.id
        logger.debug(f"ID пользователя, отправившего запрос: {user_id}")

        # Разбор callback_data
        data_parts = callback_query.data.split("_")
        logger.debug(f"Разобранные данные callback_query.data: {data_parts}")

        if len(data_parts) != 4:
            logger.error(f"Неверный формат callback_data: {callback_query.data}")
            await callback_query.answer("Ошибка: Неверный формат данных.")
            return

        _, master_id_str, date_str = data_parts[1], data_parts[2], data_parts[3]

        # Проверяем, что master_id — это число
        if not master_id_str.isdigit():
            logger.error(f"Некорректный master_id: {master_id_str}")
            await callback_query.answer("Ошибка: Некорректный идентификатор мастера.")
            return

        master_id = int(master_id_str)

        # Преобразуем строку с датой в объект datetime.date
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            logger.debug(f"Дата после преобразования: {selected_date}")
        except ValueError:
            logger.error(f"Некорректный формат даты: {date_str}")
            await callback_query.answer("Ошибка: Некорректный формат даты.")
            return

        logger.debug(f"Отображаем временные слоты для даты {selected_date} (мастер: {master_id})")

        # Переходим к отображению временных слотов
        await toggle_block_date(callback_query, master_id, selected_date)

    except Exception as e:
        logger.error(f"Ошибка при обработке callback_data {callback_query.data}: {e}")
        await callback_query.message.edit_text("Произошла ошибка. Попробуйте снова.")


async def toggle_day_block(session, master_id, selected_date, block_status):
    """Блокировка или разблокировка всего дня."""
    try:
        # Получаем записи для указанного мастера и даты
        schedules_to_update = session.query(MasterSchedule).filter(
            MasterSchedule.master_id == master_id,
            MasterSchedule.date == selected_date
        ).all()

        for schedule in schedules_to_update:
            schedule.is_blocked = block_status

        # Обновляем общее состояние дня
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
                day_of_week=selected_date.weekday() + 1,
                is_blocked=block_status
            )
            session.add(new_user_schedule)

        session.commit()
        logger.info(f"День {selected_date} {'заблокирован' if block_status else 'разблокирован'} для мастера {master_id}.")
        return True

    except Exception as e:
        logger.error(f"Ошибка при изменении состояния дня {selected_date}: {e}")
        session.rollback()
        return False


async def toggle_block_date(callback_query: CallbackQuery, master_id: int, selected_date: datetime.date):
    """Отображает временные слоты для выбранного мастера и даты."""
    start_time = 10
    end_time = 22
    time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]

    try:
        logger.info(f"Загружаем заблокированные слоты для мастера {master_id} на {selected_date}.")

        with SessionFactory() as session:
            # Получаем заблокированные временные слоты
            blocked_slots = set(
                entry.start_time.strftime('%H:%M') for entry in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.date == selected_date,
                    MasterSchedule.is_blocked == True
                ).all()
            )

            # Проверяем состояние дня
            user_schedule_entry = session.query(UserSchedule).filter(
                UserSchedule.user_id == master_id,
                UserSchedule.date == selected_date
            ).first()

            is_day_blocked = user_schedule_entry.is_blocked if user_schedule_entry else False

        logger.debug(f"Заблокированные слоты на {selected_date}: {blocked_slots}")

        # Генерация кнопок для временных слотов
        time_buttons = []
        for time in time_slots:
            if time in blocked_slots:
                time_buttons.append(
                    InlineKeyboardButton(text=f"❌ {time}", callback_data=f"unblock_time_{master_id}_{selected_date}_{time}")
                )
            else:
                time_buttons.append(
                    InlineKeyboardButton(text=f"{time}", callback_data=f"block_time_{master_id}_{selected_date}_{time}")
                )

        logger.debug(f"Кнопки для временных слотов на {selected_date}: {[btn.text for btn in time_buttons]}")

        # Добавляем кнопку закрытия/открытия дня
        if is_day_blocked:
            time_buttons.append(
                InlineKeyboardButton(text="✅ Открыть день", callback_data=f"open_day_{master_id}_{selected_date}")
            )
        else:
            time_buttons.append(
                InlineKeyboardButton(text="❌ Закрыть день", callback_data=f"close_day_{master_id}_{selected_date}")
            )

        time_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_calendar_{master_id}")
        )

        # Формируем клавиатуру
        markup = InlineKeyboardMarkup(
            inline_keyboard=[time_buttons[i:i + 3] for i in range(0, len(time_buttons), 3)]
        )

        # Обновляем сообщение
        await callback_query.message.edit_text(
            f"Выберите временные слоты для {selected_date.strftime('%d.%m.%Y')}:",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении временных слотов для {selected_date}: {e}")
        await callback_query.message.edit_text("Произошла ошибка при загрузке временных слотов.")


@router_admin.callback_query(lambda c: c.data.startswith("back_to_calendar_"))
async def back_to_calendar(callback_query: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Назад' для возвращения к календарю мастера."""
    try:
        # Извлекаем master_id из callback_data
        master_id = int(callback_query.data.split("_")[3])
        user_id = callback_query.from_user.id
        logger.info(f"Пользователь {user_id} возвращается в календарь мастера {master_id}.")

        # Генерация календаря для мастера
        calendar_markup = await generate_schedule_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось загрузить календарь для мастера {master_id}.")
            await callback_query.message.edit_text("Не удалось загрузить календарь.", reply_markup=None)
            return

        # Отправляем календарь
        await callback_query.message.edit_text(
            "Настройте расписание мастера:",
            reply_markup=calendar_markup
        )
    except Exception as e:
        logger.error(f"Ошибка при возвращении к календарю мастера: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@router_admin.callback_query(lambda c: c.data.startswith("open_day_"))
async def open_day(callback_query: CallbackQuery):
    """Открытие дня: разблокировка всех временных слотов."""
    try:
        # Разбор callback_data
        data_parts = callback_query.data.split("_")
        master_id_str, date_str = data_parts[2], data_parts[3]

        # Проверяем master_id
        if not master_id_str.isdigit():
            logger.error(f"Некорректный master_id: {master_id_str}")
            await callback_query.answer("Ошибка: Некорректный идентификатор мастера.")
            return

        master_id = int(master_id_str)

        # Проверяем дату
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Некорректный формат даты: {date_str}")
            await callback_query.answer("Ошибка: Некорректный формат даты.")
            return

        with SessionFactory() as session:
            success = await toggle_day_block(session, master_id, selected_date, block_status=False)

        if success:
            await callback_query.answer(f"День {selected_date.strftime('%d.%m.%Y')} открыт для мастера.")
            await toggle_block_date(callback_query, master_id, selected_date)
        else:
            await callback_query.message.edit_text("Произошла ошибка. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Ошибка разблокировки дня {selected_date}: {e}")
        await callback_query.message.edit_text("Произошла ошибка. Попробуйте позже.")


@router_admin.callback_query(lambda c: c.data.startswith("close_day_"))
async def close_day(callback_query: CallbackQuery):
    """Закрытие дня: блокировка всех временных слотов."""
    try:
        # Разбор callback_data
        data_parts = callback_query.data.split("_")
        master_id_str, date_str = data_parts[2], data_parts[3]

        # Проверяем master_id
        if not master_id_str.isdigit():
            logger.error(f"Некорректный master_id: {master_id_str}")
            await callback_query.answer("Ошибка: Некорректный идентификатор мастера.")
            return

        master_id = int(master_id_str)

        # Проверяем дату
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"Некорректный формат даты: {date_str}")
            await callback_query.answer("Ошибка: Некорректный формат даты.")
            return

        with SessionFactory() as session:
            success = await toggle_day_block(session, master_id, selected_date, block_status=True)

        if success:
            await callback_query.answer(f"День {selected_date.strftime('%d.%m.%Y')} заблокирован для мастера.")
            await toggle_block_date(callback_query, master_id, selected_date)
        else:
            await callback_query.message.edit_text("Произошла ошибка. Попробуйте позже.")

    except Exception as e:
        logger.error(f"Ошибка блокировки дня: {e}")
        await callback_query.message.edit_text("Произошла ошибка. Попробуйте позже.")



@router_admin.callback_query(lambda c: c.data.startswith("block_time_") or c.data.startswith("unblock_time_"))
async def block_hour(c: CallbackQuery):
    """Блокировка/разблокировка временного слота для конкретной даты."""
    try:
        # Разбор callback_data
        data_parts = c.data.split("_")
        if len(data_parts) != 5:  # Формат: block_time_{master_id}_{date}_{time}
            logger.error(f"Неверный формат callback_data: {c.data}")
            await c.answer("Ошибка: Неверный формат данных.")
            return

        action, master_id_str, date_str, time_str = data_parts[0], data_parts[2], data_parts[3], data_parts[4]

        # Проверяем master_id
        if not master_id_str.isdigit():
            logger.error(f"Некорректный master_id: {master_id_str}")
            await c.answer("Ошибка: Некорректный идентификатор мастера.")
            return

        master_id = int(master_id_str)

        # Преобразуем дату и время
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            start_time = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            logger.error(f"Некорректный формат даты или времени: {date_str}, {time_str}")
            await c.answer("Ошибка: Некорректный формат даты или времени.")
            return

        logger.debug(f"Обрабатываем {action} для {selected_date} {start_time} (мастер: {master_id})")

        with SessionFactory() as session:
            # Проверяем наличие записи в расписании
            schedule_entry = session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id,
                MasterSchedule.date == selected_date,
                MasterSchedule.start_time == start_time
            ).first()

            if schedule_entry:
                # Изменяем статус блокировки
                schedule_entry.is_blocked = not schedule_entry.is_blocked
                updated_status = "разблокирован" if not schedule_entry.is_blocked else "заблокирован"
                logger.info(f"Временной слот {start_time} {updated_status}.")
            else:
                # Если записи нет, создаём новую запись с блокировкой
                new_schedule = MasterSchedule(
                    master_id=master_id,
                    date=selected_date,
                    start_time=start_time,
                    day_of_week=selected_date.weekday() + 1,
                    is_blocked=True
                )
                session.add(new_schedule)
                logger.info(f"Создана новая запись: {selected_date} {start_time} заблокирован.")

            # Сохраняем изменения в базе данных
            session.commit()

        # Обновляем отображение временных слотов
        await toggle_block_date(c, master_id, selected_date)

    except Exception as e:
        logger.error(f"Ошибка при изменении статуса времени: {e}")
        await c.message.edit_text("Произошла ошибка. Попробуйте снова.")


async def generate_schedule_calendar(master_id, month_offset=0, state=None):
    """Генерация календаря для управления расписанием мастера."""
    now = datetime.now() + relativedelta(months=month_offset)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    start_of_month = datetime(now.year, now.month, 1).date()
    first_weekday = start_of_month.weekday()

    month_name = now.strftime('%B %Y')
    calendar_buttons = [[InlineKeyboardButton(text=month_name, callback_data="ignore")]]  # Кнопка месяца

    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    calendar_buttons.append([InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])

    # Сбор заблокированных дней для мастера и пользователей
    with SessionFactory() as session:
        try:
            blocked_dates_master = set(
                schedule.date for schedule in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.is_blocked == True,
                    MasterSchedule.date >= start_of_month,
                    MasterSchedule.date <= start_of_month + timedelta(days=days_in_month - 1)
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

            fully_blocked_dates = set(
                schedule.date for schedule in session.query(UserSchedule).filter(
                    UserSchedule.user_id == master_id,
                    UserSchedule.is_blocked == True,
                    UserSchedule.date >= start_of_month,
                    UserSchedule.date <= start_of_month + timedelta(days=days_in_month - 1)
                ).all()
            )

        except SQLAlchemyError as e:
            logger.error(f"Ошибка при запросе расписания мастера {master_id}: {e}")
            blocked_dates = set()
            fully_blocked_dates = set()

    current_day = 1
    while current_day <= days_in_month:
        week = []

        for i in range(first_weekday):
            week.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

        while current_day <= days_in_month and len(week) < 7:
            current_date = start_of_month + timedelta(days=current_day - 1)
            day_str = current_date.strftime('%d')

            # Проверка на полностью заблокированные дни (для пользователей)
            if current_date in fully_blocked_dates:
                week.append(
                    InlineKeyboardButton(text=f"{day_str}❌", callback_data=f"toggle_block_{master_id}_{current_date}"))
            # Проверка на частично заблокированные дни (для мастера и пользователей)
            elif current_date in blocked_dates:
                week.append(
                    InlineKeyboardButton(text=f"{day_str}🟠", callback_data=f"toggle_block_{master_id}_{current_date}"))
            # Блокировка прошедших дней
            elif current_date < datetime.now().date():
                week.append(InlineKeyboardButton(text=f"{day_str}❌", callback_data="ignore"))
            else:
                week.append(
                    InlineKeyboardButton(text=day_str, callback_data=f"toggle_block_{master_id}_{current_date}"))

            current_day += 1

        calendar_buttons.append(week)

        first_weekday = 0

    # Кнопки для перехода по месяцам
    calendar_buttons.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"prev_month_{month_offset - 1}"),
        InlineKeyboardButton(text="➡️", callback_data=f"next_month_{month_offset + 1}")
    ])

    if state:
        calendar_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])

    else:
        calendar_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=calendar_buttons)


@router_admin.callback_query(lambda c: c.data.startswith("prev_month_") or c.data.startswith("next_month_"))
async def change_month(callback_query: CallbackQuery, state: FSMContext):
    """
    Обработчик переключения месяца.
    """
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} переключает месяц.")

    if user_id not in ADMIN_ID:
        logger.warning(f"Пользователь {user_id} попытался переключить месяц без прав.")
        await callback_query.answer("🚫 У вас нет прав для доступа к этому меню.", show_alert=True)
        return

    # Получаем состояние (master_id)
    state_data = await state.get_data()
    master_id = state_data.get("master_id")
    if not master_id:
        logger.warning(f"Для пользователя {user_id} не выбран мастер.")
        await callback_query.answer("Выберите мастера перед изменением месяца.", show_alert=True)
        return

    # Получаем смещение месяца (из callback_data)
    month_offset = int(callback_query.data.split("_")[2])

    # Генерация календаря для выбранного мастера с новым смещением
    calendar_markup = await generate_schedule_calendar(master_id, month_offset)
    if not calendar_markup:
        logger.error(f"Не удалось загрузить календарь для мастера {master_id}.")
        await callback_query.message.edit_text("Не удалось загрузить календарь.", reply_markup=None)
        return

    # Отправляем обновленный календарь
    await callback_query.message.edit_text(
        "Настройте расписание мастера:",
        reply_markup=calendar_markup
    )
    logger.info(f"Календарь для мастера {master_id} обновлен с новым месяцем.")