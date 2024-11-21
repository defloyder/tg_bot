from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

ADMIN_ID = 475953677  # ID администратора

def main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="Информация о мастерах", callback_data="masters"),
         InlineKeyboardButton(text="Прайс лист", callback_data="get_price_list")],
        [InlineKeyboardButton(text="Записаться", callback_data="booking")],
        [InlineKeyboardButton(text="Мои записи", callback_data="my_bookings")]
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
        [InlineKeyboardButton(text="История записей", callback_data="all_booking_history")],  # Новая кнопка
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])


def my_bookings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Активные записи", callback_data="process_active_bookings")],
        [InlineKeyboardButton(text="История записей", callback_data="booking_history")],
        [InlineKeyboardButton(text="Назад", callback_data="main_menu")]
    ])
