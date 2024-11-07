from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Информация о мастерах", callback_data="masters"),
         InlineKeyboardButton(text="Прайс лист", callback_data="price_list")],
        [InlineKeyboardButton(text="Записаться", callback_data="booking", width=2)]
    ]

    if user_id == 475953677:
        buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin_panel", width=2)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="main_menu", width=7)]
    ])