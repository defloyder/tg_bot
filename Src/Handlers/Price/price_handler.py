import logging
import os

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types import FSInputFile
from sqlalchemy.exc import SQLAlchemyError

from database.database import SessionFactory
from database.models import PriceList

# Логирование
logger = logging.getLogger(__name__)


class PriceListState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    waiting_for_confirmation = State()


router_price = Router(name="price")


@router_price.callback_query(lambda c: c.data == "add_price_list")
async def add_price_list_start(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.edit_text("📝 Введите название для нового прайс-листа:")
    await state.set_state(PriceListState.waiting_for_name)


@router_price.message(PriceListState.waiting_for_name)
async def process_price_list_name(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, введите название для прайс-листа.")
        return

    await state.update_data(name=message.text)
    await message.answer("📜 Теперь введите описание для прайс-листа:")
    await state.set_state(PriceListState.waiting_for_description)


@router_price.message(PriceListState.waiting_for_description)
async def process_price_list_description(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, введите описание для прайс-листа.")
        return

    await state.update_data(price_description=message.text)
    await message.answer("📸 Теперь отправьте фотографию для прайс-листа:")
    await state.set_state(PriceListState.waiting_for_photo)


@router_price.message(PriceListState.waiting_for_photo)
async def process_price_list_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    price_description = data.get("price_description")

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

        new_price_list = PriceList(
            name=data['name'],
            price_description=price_description,
            price_photo=price_photo
        )

        with SessionFactory() as session:
            session.add(new_price_list)
            session.commit()

        await message.answer("✅ Прайс-лист успешно добавлен!")
        await state.clear()

    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении прайс-листа: {e}")
        await message.answer("⚠️ Произошла ошибка при добавлении прайс-листа.")
        await state.clear()


@router_price.callback_query(lambda c: c.data == "view_price_lists")
async def view_price_lists(callback_query: CallbackQuery):
    logger.info("view_price_lists callback triggered.")
    try:
        with SessionFactory() as session:
            price_lists = session.query(PriceList).all()

        if price_lists:
            buttons = [
                [InlineKeyboardButton(text=price_list.name, callback_data=f"view_price_{price_list.price_id}")]
                for price_list in price_lists
            ]
            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            try:
                # Удаление старого сообщения
                await callback_query.message.delete()
            except Exception as e:
                # Если не удалось удалить сообщение, логируем ошибку
                logger.error(f"Ошибка при удалении старого сообщения: {e}")

            # Отправляем новое сообщение с меню
            await callback_query.message.answer("Выберите прайс-лист для просмотра:", reply_markup=markup)
        else:
            # Если прайс-листы не найдены, удаляем старое сообщение и показываем уведомление
            try:
                await callback_query.message.delete()
            except Exception as e:
                logger.error(f"Ошибка при удалении старого сообщения: {e}")

            await callback_query.message.answer("⚠️ Прайс-листы не найдены.")
    except Exception as e:
        logger.error(f"Ошибка при получении прайс-листов: {e}")
        try:
            # Удаляем старое сообщение и показываем ошибку
            await callback_query.message.delete()
        except Exception as e:
            logger.error(f"Ошибка при удалении старого сообщения: {e}")

        await callback_query.message.answer("⚠️ Произошла ошибка при загрузке прайс-листов.")


@router_price.callback_query(lambda c: c.data.startswith("view_price_"))
async def show_price_list(callback_query: CallbackQuery):
    price_list_id = int(callback_query.data.split("_")[-1])

    with SessionFactory() as session:
        price_list = session.query(PriceList).filter_by(price_id=price_list_id).first()

    if price_list:
        description = price_list.price_description
        price_photo = price_list.price_photo
        back_button = InlineKeyboardButton(text="⬅️ Назад", callback_data="view_price_lists")
        markup = InlineKeyboardMarkup(inline_keyboard=[[back_button]])

        if os.path.exists(price_photo):
            input_file = FSInputFile(price_photo, filename=os.path.basename(price_photo))
            await callback_query.message.edit_media(
                media=types.InputMediaPhoto(media=input_file, caption=f"{description}"),  # Именованный аргумент 'media'
                reply_markup=markup
            )
        else:
            await callback_query.message.edit_text(f"{description}", reply_markup=markup)
    else:
        await callback_query.message.edit_text("⚠️ Прайс-лист не найден.")


@router_price.callback_query(lambda c: c.data == "delete_price_list")
async def delete_price_list_start(callback_query: CallbackQuery):
    await callback_query.answer()
    try:
        with SessionFactory() as session:
            price_lists = session.query(PriceList).all()

        if price_lists:
            buttons = [
                [InlineKeyboardButton(text=price_list.name,
                                      callback_data=f"confirm_delete_price_{price_list.price_id}")]
                for price_list in price_lists
            ]
            buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)

            await callback_query.message.edit_text("Выберите прайс-лист для удаления:", reply_markup=markup)
        else:
            await callback_query.message.answer("⚠️ Прайс-листы не найдены.")
    except Exception as e:
        logger.error(f"Ошибка при получении прайс-листов для удаления: {e}")
        await callback_query.message.answer("⚠️ Произошла ошибка при загрузке прайс-листов.")


@router_price.callback_query(lambda c: c.data.startswith("confirm_delete_price_"))
async def confirm_price_list_deletion(callback_query: CallbackQuery):
    try:
        # Извлекаем price_list_id из callback_data
        price_list_id = int(callback_query.data.split("_")[-1])
    except (IndexError, ValueError) as e:
        logger.error(f"Ошибка при извлечении price_list_id из callback {callback_query.data}: {e}")
        await callback_query.answer("Ошибка при обработке запроса. Попробуйте снова.", show_alert=True)
        return

    try:
        with SessionFactory() as session:
            price_list = session.query(PriceList).filter_by(price_id=price_list_id).first()
            if price_list:
                session.delete(price_list)
                session.commit()
                await callback_query.message.answer("✅ Прайс-лист успешно удалён!")
            else:
                await callback_query.message.answer("⚠️ Прайс-лист не найден.")
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при удалении прайс-листа: {e}")
        await callback_query.message.answer("⚠️ Произошла ошибка при удалении прайс-листа.")
