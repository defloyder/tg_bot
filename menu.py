import logging

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import Master
from database.database import SessionFactory

ADMIN_ID = [475953677, 962757762]


async def main_menu(user_id):
    """Главное меню для пользователя."""
    try:
        with SessionFactory() as session:
            master_exists = session.query(Master).filter(Master.master_id == user_id).first()

            if master_exists:
                return await updated_master_menu(user_id)

        buttons = [
            [
                InlineKeyboardButton(text="ℹ️ О мастерах", callback_data="masters"),
                InlineKeyboardButton(text="💰 Прайс-лист", callback_data="view_price_lists")
            ],
            [InlineKeyboardButton(text="📅 Записаться на приём", callback_data="booking")],
            [InlineKeyboardButton(text="📝 Мои записи", callback_data="my_bookings")]
        ]

        if user_id in ADMIN_ID:
            buttons.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    except Exception as e:
        logging.error(f"Ошибка при извлечении мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Возникла ошибка", callback_data="error")]
        ])


async def updated_master_menu(user_id):
    """Обновленное меню для мастеров с учетом админ-панели, если пользователь является администратором."""
    try:
        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == user_id).first()

            if master:
                menu_buttons = [
                    [InlineKeyboardButton(text="🟢 Активные записи", callback_data="active_bookings")],
                    [InlineKeyboardButton(text="📖 История записей", callback_data="booking_history")],
                    [InlineKeyboardButton(text="📋 Прайс-лист", callback_data="view_price_lists")],
                    [InlineKeyboardButton(text="🔲 Управление окошками", callback_data="windows")]
                ]

                if user_id in ADMIN_ID:
                    menu_buttons.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])

                return InlineKeyboardMarkup(inline_keyboard=menu_buttons)
            else:
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚠️ Этот мастер был удалён", callback_data="main_menu")]
                ])
    except Exception as e:
        logging.error(f"Ошибка при проверке мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Возникла ошибка", callback_data="error")]
        ])


def back_to_master_menu():
    """Кнопка возврата в меню мастера."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в меню мастера", callback_data="master_menu")]
    ])


def back_to_main_menu():
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])


def my_bookings_menu():
    """Меню записей пользователя."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Активные записи", callback_data="active_bookings")],
        [InlineKeyboardButton(text="📖 История записей", callback_data="booking_history")],
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])



def admin_panel():
    """Меню администратора."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👸 Настройка мастеров", callback_data="open_settings")],  # Новая кнопка
        [InlineKeyboardButton(text="⚙️ Настройка прайс-листов", callback_data="price_list_settings")],
        [InlineKeyboardButton(text="📜 История всех записей", callback_data="all_booking_history")],
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])

def open_settings_menu():
    """Меню настройки мастеров."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить мастера", callback_data="add_master")],
        [InlineKeyboardButton(text="✏️ Редактировать мастера", callback_data="edit_master")],
        [InlineKeyboardButton(text="❌ Удалить мастера", callback_data="delete_master")],
        [InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")]
    ])

def price_list_settings_menu():
    """Меню настройки прайс-листов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить прайс-лист", callback_data="add_price_list")],
        [InlineKeyboardButton(text="❌ Удалить прайс-лист", callback_data="delete_price_list")],
        [InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")]
    ])