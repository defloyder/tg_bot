from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
from Src.Handlers.Booking.service import generate_calendar  # Убедитесь, что это правильно настроено
from database import Booking, Master
from database.database import SessionFactory
from logger_config import logger
from menu import ADMIN_ID

router_booking = Router(name="booking")

# Обработчик кнопки "Записаться"
@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик кнопки 'Записаться' запущен.")
    await callback_query.answer()

    try:
        # Получаем список мастеров из базы данных
        with SessionFactory() as session:
            masters = session.query(Master).all()

        if masters:
            buttons = [
                [InlineKeyboardButton(text=master.master_name, callback_data=f"booking_master_{master.master_id}")]
                for master in masters
            ]
            buttons.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])  # Кнопка назад
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("Выберите мастера для записи:", reply_markup=keyboard)
            logger.debug("Отправлено меню выбора мастеров для записи.")
        else:
            await callback_query.message.edit_text("Нет доступных мастеров для записи.")
            logger.warning("Список мастеров пуст.")
    except Exception as e:
        logger.error(f"Ошибка при получении списка мастеров: {e}")
        await callback_query.answer("Произошла ошибка при получении списка мастеров.", show_alert=True)

# Обработчик выбора мастера
@router_booking.callback_query(lambda c: c.data.startswith('booking_master_'))
async def process_booking_master(callback_query: CallbackQuery):
    try:
        master_id = int(callback_query.data.split('_')[-1])  # Приводим master_id к числу
        logger.info(f"Пользователь выбрал мастера с ID {master_id} для записи.")
        await callback_query.answer()

        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == master_id).first()

            if not master:
                logger.error(f"Мастер с ID {master_id} не найден в базе данных.")
                await callback_query.message.edit_text("Мастер не найден. Попробуйте снова.")
                return

        # Генерация календаря для выбранного мастера
        calendar_markup = await generate_calendar(master_id=master_id)
        await callback_query.message.edit_text(
            f"Выберите дату для записи к мастеру {master.master_name}:",
            reply_markup=calendar_markup
        )
        logger.debug(f"Календарь для мастера {master.master_name} успешно отправлен.")
    except ValueError:
        logger.error(f"Ошибка преобразования master_id: {callback_query.data.split('_')[-1]}")
        await callback_query.message.edit_text("Ошибка в данных мастера. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора мастера: {e}")
        await callback_query.answer("Произошла ошибка при обработке мастера. Попробуйте позже.", show_alert=True)

# Обработчик выбора даты
@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_booking_date(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id = data[1]
    selected_date = data[2]
    logger.info(f"Пользователь выбрал дату {selected_date} для мастера ID {master_id}.")
    await callback_query.answer()

    try:
        # Кнопки для выбора времени
        time_buttons = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="10:00", callback_data=f"time_{master_id}_{selected_date}_10:00"),
             InlineKeyboardButton(text="11:00", callback_data=f"time_{master_id}_{selected_date}_11:00")],
            [InlineKeyboardButton(text="14:00", callback_data=f"time_{master_id}_{selected_date}_14:00"),
             InlineKeyboardButton(text="15:00", callback_data=f"time_{master_id}_{selected_date}_15:00")],
            [InlineKeyboardButton(text="Назад", callback_data=f"booking_master_{master_id}")]
        ])

        await callback_query.message.edit_text(
            f"Выберите время для записи с мастером ID {master_id} на {selected_date}:",
            reply_markup=time_buttons
        )
        logger.debug(f"Время для мастера ID {master_id} на {selected_date} предложено.")
    except Exception as e:
        logger.error(f"Ошибка при обработке выбора даты {selected_date} для мастера ID {master_id}: {e}")
        await callback_query.answer("Произошла ошибка при выборе времени.", show_alert=True)

# Обработчик выбора времени
@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_booking_time(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id, selected_date, selected_time = data[1], data[2], data[3]
    datetime_value = f"{selected_date} {selected_time}"
    logger.info(f"Пользователь выбрал время {datetime_value} для мастера ID {master_id}.")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            # Проверка занятости времени
            existing_record = session.query(Booking).filter_by(
                booking_datetime=datetime.strptime(datetime_value, "%Y-%m-%d %H:%M"),
                master=master_id
            ).first()

            if existing_record:
                await callback_query.answer("Это время уже занято.", show_alert=True)
                logger.debug(f"Время {datetime_value} для мастера ID {master_id} занято.")
                return

            # Создаем запись
            new_record = Booking(
                booking_datetime=datetime.strptime(datetime_value, "%Y-%m-%d %H:%M"),
                master=master_id
            )
            session.add(new_record)
            session.commit()
            logger.info(f"Запись успешно создана: {new_record}")

    except Exception as e:
        logger.error(f"Ошибка при записи на {datetime_value} для мастера ID {master_id}: {e}")
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
        return

    # Подтверждение записи
    confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text(
        f"Запись подтверждена!\nМастер ID: {master_id}\nДата: {selected_date}\nВремя: {selected_time}",
        reply_markup=confirm_menu
    )
    logger.debug(f"Подтверждение записи отправлено: мастер ID {master_id}, дата {selected_date}, время {selected_time}.")

# Обработчик кнопки "Информация о мастерах"
@router_booking.callback_query(lambda c: c.data == "masters")
async def show_masters_list(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Информация о мастерах' запущен.")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            masters = session.query(Master).all()  # Получение всех мастеров из базы данных

        if masters:
            buttons = [
                [InlineKeyboardButton(text=master.master_name, callback_data=f"master_{master.master_id}")]
                for master in masters
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text(
                "Выберите мастера, чтобы узнать подробности:",
                reply_markup=keyboard
            )
            logger.debug("Отправлен список мастеров.")
        else:
            await callback_query.message.edit_text("Нет доступных мастеров.")
            logger.warning("Список мастеров пуст.")
    except Exception as e:
        logger.error(f"Ошибка при получении списка мастеров: {e}")
        await callback_query.answer("Произошла ошибка при получении списка мастеров.", show_alert=True)
