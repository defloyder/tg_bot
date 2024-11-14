from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton


from logger_config import logger
from menu import admin_panel, back_to_main_menu, main_menu

router_admin = Router(name="admin")

ADMIN_ID = 475953677


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


@router_admin.callback_query(lambda c: c.data == "main_menu")
async def main_menu_handler(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if user_id == ADMIN_ID:
        await callback_query.answer()
        await callback_query.message.edit_text(
            "Вы в главном меню. Выберите нужную опцию.", reply_markup=main_menu(user_id)
        )
        logger.info(f"Администратор {user_id} вернулся в главное меню.")
    else:
        await callback_query.message.edit_text(
            "Вы в главном меню. Выберите нужную опцию.", reply_markup=main_menu(user_id)
        )
        logger.info(f"Пользователь {user_id} вернулся в главное меню.")
