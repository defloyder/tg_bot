
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

    with SessionFactory() as session:
        create_user(session=session, event=message )
    await message.answer("Добро пожаловать! Нажмите 'Начать' для продолжения.", reply_markup=main_menu(user_id))
