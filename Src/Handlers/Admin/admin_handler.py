from aiogram import Router, types
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, ContentType
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy.exc import IntegrityError

from database import Master
from database.database import SessionFactory
from database.repository import create_master, update_master, get_master_by_id, delete_master
from menu import admin_panel, back_to_main_menu
from logger_config import logger

router_admin = Router(name="admin")

ADMIN_ID = 475953677


class AddMasterStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    confirmation = State()


class EditMasterStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    confirmation = State()


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


@router_admin.callback_query(lambda c: c.data == "add_master")
async def start_adding_master(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        await callback_query.answer()
        await callback_query.message.edit_text("Введите имя мастера (или напишите 'отмена' для отмены):")
        await state.set_state(AddMasterStates.waiting_for_name)
        logger.info(f"Администратор {user_id} начал добавление нового мастера.")
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} попытался добавить мастера.")


@router_admin.message(AddMasterStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Процесс добавления мастера отменен.")
        return

    master_name = message.text.strip()
    if not master_name:
        await message.answer("Имя не может быть пустым. Попробуйте снова.")
        return

    await state.update_data(master_name=master_name)
    await message.answer("Теперь введите описание мастера (или напишите 'пропустить' для пропуска):")
    await state.set_state(AddMasterStates.waiting_for_description)


@router_admin.message(AddMasterStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Процесс добавления мастера отменен.")
        return

    description = message.text.strip()
    if description.lower() == "пропустить":
        description = "Описание не задано"

    await state.update_data(master_description=description)
    await message.answer("Отправьте фото мастера:")
    await state.set_state(AddMasterStates.waiting_for_photo)


@router_admin.message(AddMasterStates.waiting_for_photo)
async def process_photo(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Процесс добавления мастера отменен.")
        return

    if message.photo:
        photo_id = message.photo[-1].file_id
        await state.update_data(master_photo=photo_id)
        await message.answer("Мастер добавлен! Подтвердите, если всё верно (да/нет):")
        await state.set_state(AddMasterStates.confirmation)
    else:
        await message.answer("Пожалуйста, отправьте фото.")



@router_admin.message(AddMasterStates.confirmation)
async def confirm_master_addition(message: Message, state: FSMContext):
    if message.text.lower() == "да":
        data = await state.get_data()
        master_name = data.get("master_name")
        master_description = data.get("master_description")
        master_photo = data.get("master_photo")

        with SessionFactory() as session:
            existing_master = session.query(Master).filter(Master.master_name == master_name).first()

            if existing_master:
                await message.answer(f"Мастер с именем '{master_name}' уже существует!")
                logger.error(f"Мастер с именем '{master_name}' уже существует.")
                return

            try:
                new_master = create_master(session, master_name=master_name, master_description=master_description,
                                           master_photo=master_photo)
                session.commit()
                logger.info(f"Добавлен новый мастер: {new_master.master_name} (ID: {new_master.master_id})")
                await message.answer(f"Мастер {new_master.master_name} успешно добавлен!")
            except IntegrityError as e:
                session.rollback()
                await message.answer("Произошла ошибка при добавлении мастера. Попробуйте снова.")
                logger.error(f"Ошибка при добавлении мастера: {e}")

        await state.clear()
    elif message.text.lower() == "нет":
        await state.clear()
        await message.answer("Процесс добавления мастера отменен.")
    else:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.")


@router_admin.callback_query(lambda c: c.data == "edit_master")
async def edit_master(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        await callback_query.answer()

        with SessionFactory() as session:
            masters = session.query(Master).all()
            if not masters:
                await callback_query.message.edit_text("Нет мастеров для редактирования.")
                return

            keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[])

            for master in masters:
                # Проверяем, что master_name не None и не пустое
                master_name = master.master_name if master.master_name else "Без имени"
                keyboard.inline_keyboard.append(
                    [InlineKeyboardButton(text=master_name, callback_data=f"edit_{master.master_id}")])

            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])
            await callback_query.message.edit_text("Выберите мастера для редактирования:", reply_markup=keyboard)
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} пытался редактировать мастера.")


@router_admin.callback_query(lambda c: c.data.startswith("edit_"))
async def handle_master_edit(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    if user_id == ADMIN_ID:
        master_id = int(callback_query.data.split("_")[1])

        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == master_id).first()

            if master:
                # Начнем редактирование
                await state.set_state(EditMasterStates.waiting_for_name)
                await state.update_data(master_id=master.master_id,
                                        master_name=master.master_name,
                                        master_description=master.master_description,
                                        master_photo=master.master_photo)

                await callback_query.answer()
                await callback_query.message.edit_text(
                    f"Вы выбрали мастера: {master.master_name}\n\nОписание: {master.master_description}\nФото: {master.master_photo}\n\nВведите новое имя (или напишите 'пропустить' для пропуска):")
            else:
                await callback_query.answer("Мастер не найден.", show_alert=True)
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {user_id} пытался редактировать мастера.")


@router_admin.message(EditMasterStates.waiting_for_name)
async def process_name_edit(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Процесс редактирования отменен.")
        return

    new_name = message.text.strip()
    if new_name.lower() == "пропустить":
        new_name = None  # Оставим старое имя, если не меняем

    data = await state.get_data()
    master_id = data["master_id"]
    with SessionFactory() as session:
        master = session.query(Master).filter(Master.master_id == master_id).first()
        if master:
            if new_name:
                master.master_name = new_name
            await state.update_data(master_name=new_name)
            await message.answer("Теперь введите описание мастера (или напишите 'пропустить' для пропуска):")
            await state.set_state(EditMasterStates.waiting_for_description)


@router_admin.message(EditMasterStates.waiting_for_description)
async def process_description_edit(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Процесс редактирования отменен.")
        return

    new_description = message.text.strip()
    if new_description.lower() == "пропустить":
        new_description = None  # Оставим старое описание, если не меняем

    data = await state.get_data()
    master_id = data["master_id"]
    with SessionFactory() as session:
        master = session.query(Master).filter(Master.master_id == master_id).first()
        if master:
            if new_description:
                master.master_description = new_description
            await state.update_data(master_description=new_description)
            await message.answer("Теперь отправьте новое фото мастера (или напишите 'пропустить' для пропуска):")
            await state.set_state(EditMasterStates.waiting_for_photo)

    @router_admin.message(EditMasterStates.waiting_for_photo)
    async def process_photo_edit(message: Message, state: FSMContext):
        if message.text and message.text.lower() == "отмена":
            await state.clear()
            await message.answer("Процесс редактирования мастера отменен.")
            return

        if message.photo:
            photo_id = message.photo[-1].file_id
            await state.update_data(master_photo=photo_id)
            await message.answer("Фото мастера обновлено! Подтвердите, если всё верно (да/нет):")
            await state.set_state(EditMasterStates.confirmation)
        else:
            await message.answer("Пожалуйста, отправьте фото.")


@router_admin.message(EditMasterStates.confirmation)
async def confirm_master_edit(message: Message, state: FSMContext):
    if message.text.lower() == "да":
        data = await state.get_data()
        master_name = data.get("master_name")
        master_description = data.get("master_description")
        master_photo = data.get("master_photo")

        with SessionFactory() as session:
            master_id = data["master_id"]
            master = session.query(Master).filter(Master.master_id == master_id).first()
            if master:
                # Обновляем данные мастера в базе данных
                master.master_name = master_name if master_name else master.master_name
                master.master_description = master_description if master_description else master.master_description
                master.master_photo = master_photo if master_photo else master.master_photo
                session.commit()
                logger.info(f"Мастер {master.master_name} (ID: {master.master_id}) был успешно обновлен!")
                await message.answer(f"Мастер {master.master_name} успешно обновлен!")
            else:
                await message.answer("Произошла ошибка, мастер не найден.")

        await state.clear()
    elif message.text.lower() == "нет":
        await state.clear()
        await message.answer("Редактирование мастера отменено.")
    else:
        await message.answer("Пожалуйста, ответьте 'да' или 'нет'.")


@router_admin.callback_query(lambda c: c.data == "delete_master")
async def delete_master(callback_query: CallbackQuery, state: FSMContext):
    if callback_query.from_user.id == ADMIN_ID:  # Проверка прав администратора
        # Получаем список всех мастеров из базы данных
        with SessionFactory() as session:
            masters = session.query(Master).all()
            if not masters:
                await callback_query.message.edit_text("Нет мастеров для удаления.")
                return

            keyboard = InlineKeyboardMarkup(row_width=2, inline_keyboard=[])

            # Добавляем кнопки для каждого мастера с их ID
            for master in masters:
                master_name = master.master_name if master.master_name else "Без имени"
                keyboard.inline_keyboard.append(
                    [InlineKeyboardButton(text=master_name, callback_data=f"confirm_delete_{master.master_id}")])

            keyboard.inline_keyboard.append([InlineKeyboardButton(text="Назад", callback_data="main_menu")])
            await callback_query.message.edit_text("Выберите мастера для удаления:", reply_markup=keyboard)
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)


@router_admin.callback_query(lambda c: c.data.startswith("confirm_delete_"))
async def confirm_master_deletion(callback_query: CallbackQuery, state: FSMContext):
    if callback_query.from_user.id == ADMIN_ID:  # Проверка прав администратора
        master_id = int(callback_query.data.split("_")[2])

        # Логируем действие
        logger.info(f"Админ {callback_query.from_user.id} инициировал удаление мастера с ID {master_id}")

        # Синхронная сессия для удаления мастера
        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == master_id).first()

            if master:
                try:
                    # Удаляем мастера и коммитим транзакцию
                    session.delete(master)
                    session.commit()

                    logger.info(f"Мастер {master.master_name} (ID: {master.master_id}) был удален.")
                    await callback_query.message.edit_text(f"Мастер {master.master_name} успешно удален!")
                except Exception as e:
                    session.rollback()
                    logger.error(f"Ошибка при удалении мастера {master.master_name}: {e}")
                    await callback_query.message.edit_text(f"Ошибка при удалении мастера. Попробуйте снова.")
            else:
                await callback_query.message.edit_text("Мастер не найден.")
    else:
        await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
        logger.warning(f"Пользователь {callback_query.from_user.id} пытался удалить мастера, но не является администратором.")