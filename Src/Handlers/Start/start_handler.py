import logging

from aiogram import Router,types
from aiogram.filters import CommandStart

from database.database import SessionFactory
from database.repository import create_user
from menu import main_menu

router_start = Router(name="start")

@router_start.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Создание нового пользователя в базе данных
    try:
        with SessionFactory() as session:
            create_user(session=session, event=message)

        # Получаем клавиатуру для пользователя
        reply_markup = await main_menu(user_id)  # здесь добавляем await, так как main_menu возвращает корутину

        # Отправляем приветственное сообщение с меню
        await message.answer("Добро пожаловать! Нажмите 'Начать' для продолжения.", reply_markup=reply_markup)

    except Exception as e:
        logging.error(f"Ошибка при обработке команды /start: {e}")
        await message.answer("Произошла ошибка, попробуйте позже.")