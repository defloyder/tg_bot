import logging
from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database.database import SessionFactory
from database.repository import create_user
from menu import main_menu

router_start = Router(name="start")

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🏚️ Главное меню")]],
    resize_keyboard=True
)

@router_start.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    try:
        with SessionFactory() as session:
            create_user(session=session, event=message)

        reply_markup = await main_menu(user_id)

        await message.answer(
            "Добро пожаловать! Нажмите 'Главное меню' для перехода в меню управления.",
            reply_markup=start_keyboard
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке команды /start: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")

@router_start.message(lambda message: message.text == "🏚️ Главное меню")
async def start_button_pressed(message: types.Message):
    user_id = message.from_user.id

    try:
        with SessionFactory() as session:
            create_user(session=session, event=message)

        reply_markup = await main_menu(user_id)

        await message.answer(
            "Добро пожаловать! Нажмите 'Начать' для продолжения.",
            reply_markup=reply_markup
        )

    except Exception as e:
        logging.error(f"Ошибка при обработке нажатия кнопки 'Начать': {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")
