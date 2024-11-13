from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputFile
from datetime import datetime
from Src.Handlers.Booking.service import generate_calendar
from database import Booking, Master
from database.database import SessionFactory
from database.repository import create_record
from logger_config import logger
from menu import ADMIN_ID

router_booking = Router(name="booking")

# Обработчик нажатия кнопки "Записаться"
@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")
    await callback_query.answer()

    master_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Арина", callback_data="master_1"),
         InlineKeyboardButton(text="Маша", callback_data="master_2")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text("Выберите мастера:", reply_markup=master_menu)
    logger.debug("Отправлено меню с выбором мастера.")

@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master(callback_query: CallbackQuery):
    master_id = callback_query.data.split('_')[1]  # Получаем ID мастера
    logger.debug(f"Пользователь выбрал мастера с ID: {master_id}")
    await callback_query.answer()

    try:
        # Получаем информацию о мастере из базы данных
        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == master_id).first()

        if master:
            # Формируем сообщение с информацией о мастере
            message = f"Информация о мастере {master.master_name}:\n\n" \
                      f"Описание: {master.master_description}\n"

            if master.master_photo:  # Если есть фото
                # Проверяем, если это ID изображения в Telegram
                if master.master_photo.startswith("AgACAgIAAxkBAA"):  # ID фотографии Telegram
                    await callback_query.message.answer_photo(master.master_photo, caption=message)
                else:  # Если это URL
                    message += f"Фото: {master.master_photo}"  # Предположим, что это URL фото
                    await callback_query.message.edit_text(message)
            else:
                message += "Фото: Нет фото"
                await callback_query.message.edit_text(message)

            # Кнопки для выбора времени (или можно добавить другую логику, если хотите)
            time_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Выбрать время", callback_data=f"choose_time_{master_id}")],
                [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
            ])
            # Отправляем информацию о мастере
            logger.debug(f"Отправлена информация о мастере {master.master_name}")
        else:
            await callback_query.message.edit_text("Мастер не найден.")
            logger.warning(f"Мастер с ID {master_id} не найден.")
    except Exception as e:
        logger.error(f"Ошибка при получении информации о мастере {master_id}: {e}")
        await callback_query.answer("Произошла ошибка при получении информации о мастере.", show_alert=True)

# Обработчик выбора времени для записи
@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    data = callback_query.data.split('_')
    master_id, date, time = data[1], data[2], data[3]
    logger.debug(f"Пользователь выбрал время для записи: {date} {time}, мастер ID: {master_id}")
    await callback_query.answer()

    datetime_value = f"{date} {time}"
    try:
        with SessionFactory() as session:
            existing_record = session.query(Booking).filter_by(
                booking_datetime=datetime_value,
                master=master_id
            ).first()

            if existing_record:
                await callback_query.answer("Это время уже занято.", show_alert=True)
                logger.debug(f"Время {datetime_value} уже занято.")
                return

            # Создаем запись в базе данных
            new_record = create_record(session=session, datetime_value=datetime_value, master=master_id)
            if not new_record:
                await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
                logger.error(f"Ошибка при создании записи для {datetime_value}.")
                return

            logger.info(f"Запись успешно создана: {new_record}")
    except Exception as e:
        logger.error(f"Ошибка при записи на {datetime_value}: {e}")
        await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
        return

    # Подтверждение записи
    confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
    ])
    await callback_query.message.edit_text(
        f"Запись подтверждена!\nМастер: {master_id}\nДата: {date}\nВремя: {time}",
        reply_markup=confirm_menu
    )
    logger.debug(f"Подтверждение записи отправлено: мастер ID {master_id}, дата {date}, время {time}.")

# Обработчик отображения списка мастеров для админа
@router_booking.callback_query(lambda c: c.data == "masters")
async def show_masters_list(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        await callback_query.answer()

        # Получаем всех мастеров из базы данных
        with SessionFactory() as session:
            masters = session.query(Master).all()  # Запрос на получение всех мастеров

        # Если мастера есть
        if masters:
            buttons = [
                [InlineKeyboardButton(text=master.master_name, callback_data=f"master_{master.master_id}") for master in
                 masters]
            ]
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            # Отправляем список мастеров
            await callback_query.message.edit_text(
                "Выберите мастера, чтобы узнать подробности:",
                reply_markup=keyboard
            )
        else:
            await callback_query.message.edit_text("Нет доступных мастеров.")
            logger.warning(f"Администратор {user_id} запросил список мастеров, но их нет в базе.")
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} попытался получить информацию о мастерах.")
