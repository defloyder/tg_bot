from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

ADMIN_ID = 475953677  # ID администратора

def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Информация о мастерах", callback_data="masters"),
         InlineKeyboardButton(text="Прайс лист", callback_data="price_list")],
        [InlineKeyboardButton(text="Записаться", callback_data="booking")]
    ]

    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# Кнопка "Назад" в меню
def back_to_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])

def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить мастера", callback_data="add_master")],
        [InlineKeyboardButton(text="Редактировать мастера", callback_data="edit_master")],
        [InlineKeyboardButton(text="Удалить мастера", callback_data="delete_master")],
        [InlineKeyboardButton(text="Редактировать прайс-лист", callback_data="edit_price_list")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])
