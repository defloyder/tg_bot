from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.filters import Command

from database import Master
from logger_config import logger
from database.database import SessionFactory
from database.repository import create_master, update_master, get_master_by_id, delete_master

router_master = Router(name="masters")

# Обработчик вызова редактирования информации о мастерах
@router_master.callback_query(lambda c: c.data == 'edit_masters_info')
async def process_callback_edit_masters_info(callback_query: CallbackQuery):
    logger.debug("Запущен обработчик редактирования информации о мастерах.")
    await callback_query.answer()
    await callback_query.message.edit_text(
        "Введите информацию о мастерах командой /add_master в формате:\nИмя, Описание\nПовторите для каждого мастера."
    )
    logger.info("Ожидается ввод данных для добавления мастеров.")

# Обработчик для добавления мастера
@router_master.message(Command("add_master"))
async def add_master(message: Message):
    try:
        master_info = message.text.split(', ')
        if len(master_info) < 2:
            await message.answer("Ошибка: введите данные в формате Имя, Описание.")
            return

        master_name, master_description = master_info[0], master_info[1]
        with SessionFactory() as session:
            new_master = create_master(session, master_name=master_name, master_description=master_description)
            logger.info(f"Создан новый мастер: {new_master.master_name} (ID: {new_master.master_id})")
        await message.answer(f"Мастер {master_name} добавлен.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении мастера: {e}")
        await message.answer("Ошибка при добавлении мастера. Попробуйте снова.")
# Обработчик для отображения информации о мастерах
@router_master.callback_query(lambda c: c.data == 'masters')
async def show_masters(callback_query: CallbackQuery):
    logger.debug("Запущен обработчик отображения информации о мастерах.")
    try:
        with SessionFactory() as session:
            masters = session.query(Master).all()

        if not masters:
            await callback_query.message.edit_text("Список мастеров пуст.")
            logger.info("Список мастеров пуст.")
            return

        master_buttons = [
            [InlineKeyboardButton(text=master.master_name, callback_data=f"show_master_{master.master_id}")]
            for master in masters
        ]
        master_buttons.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])
        markup = InlineKeyboardMarkup(inline_keyboard=master_buttons)

        await callback_query.answer()
        await callback_query.message.edit_text(
            "Выберите мастера для просмотра информации:", reply_markup=markup
        )
        logger.info("Меню мастеров успешно отображено.")
    except Exception as e:
        logger.error(f"Ошибка при получении списка мастеров: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

# Обработчик для отображения информации выбранного мастера
@router_master.callback_query(lambda c: c.data.startswith('show_master_'))
async def show_selected_master(callback_query: CallbackQuery):
    master_id = int(callback_query.data.split('_')[-1])
    logger.debug(f"Запрошена информация о мастере с ID: {master_id}")

    try:
        with SessionFactory() as session:
            master = get_master_by_id(session, master_id)

        if not master:
            await callback_query.answer("Мастер не найден.", show_alert=True)
            logger.error(f"Мастер с ID {master_id} не найден.")
            return

        description = master.master_description or "Описание пока не добавлено."
        photo_file_id = master.master_photo
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="masters")]
        ])
        await callback_query.answer()

        if photo_file_id:
            await callback_query.message.answer_photo(
                photo=photo_file_id, caption=f"{master.master_name}\n\n{description}", reply_markup=markup
            )
        else:
            await callback_query.message.answer(
                text=f"{master.master_name}\n\n{description}", reply_markup=markup
            )
        await callback_query.message.delete()
        logger.info(f"Информация о мастере {master.master_name} (ID: {master_id}) отправлена пользователю.")
    except Exception as e:
        logger.error(f"Ошибка при получении информации о мастере с ID {master_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

# Обработчик вызова обновления информации о мастере
@router_master.callback_query(lambda c: c.data.startswith('edit_master_'))
async def process_edit_master(callback_query: CallbackQuery):
    master_id = int(callback_query.data.split('_')[-1])
    logger.debug(f"Запущен режим редактирования мастера с ID: {master_id}")

    try:
        with SessionFactory() as session:
            master = get_master_by_id(session, master_id)

        if not master:
            await callback_query.answer("Мастер не найден.", show_alert=True)
            logger.error(f"Мастер с ID {master_id} не найден.")
            return

        await callback_query.message.edit_text(
            f"Редактирование мастера {master.master_name}.\n"
            f"Отправьте новое описание или фото в формате:\n"
            f"/update_master [Описание] или отправьте фото."
        )
        # Храним ID мастера в атрибуте callback_query для дальнейшего обновления
        callback_query.message.chat['current_editing_master'] = master_id
        logger.info(f"Готов к редактированию мастера с ID {master_id}.")
    except Exception as e:
        logger.error(f"Ошибка при запуске редактирования мастера с ID {master_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

# Обработчик для обновления описания или фото мастера
@router_master.message(Command("update_master"))
async def update_master_description(message: Message):
    master_id = message.chat.get('current_editing_master')
    if not master_id:
        await message.answer("Сначала выберите мастера для редактирования через меню.")
        return

    description = message.text.replace('/update_master', '').strip()
    try:
        with SessionFactory() as session:
            updated_master = update_master(session, master_id, master_description=description)
        await message.answer(f"Описание мастера {updated_master.master_name} обновлено.")
        logger.info(f"Мастер с ID {master_id} успешно обновлен.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении мастера с ID {master_id}: {e}")
        await message.answer("Произошла ошибка при обновлении мастера.")
