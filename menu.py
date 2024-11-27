from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from database import Master
from database.database import SessionFactory
import logging

# Идентификаторы администраторов
ADMIN_ID = [475953677, 962757762]

async def main_menu(user_id):
    """Главное меню для пользователя."""
    try:
        with SessionFactory() as session:
            # Проверяем, является ли пользователь мастером
            master_exists = session.query(Master).filter(Master.master_id == user_id).first()

            if master_exists:
                return await updated_master_menu(user_id)

        # Кнопки для обычных пользователей
        buttons = [
            [
                InlineKeyboardButton(text="ℹ️ Узнать о мастерах", callback_data="masters"),
                InlineKeyboardButton(text="💰 Прайс-лист", callback_data="get_price_list")
            ],
            [InlineKeyboardButton(text="📅 Записаться на приём", callback_data="booking")],
            [InlineKeyboardButton(text="📝 Мои записи", callback_data="my_bookings")]
        ]

        # Добавляем админ-панель для администраторов
        if user_id in ADMIN_ID:
            buttons.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    except Exception as e:
        logging.error(f"Ошибка при извлечении мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[  # если произошла ошибка
            [InlineKeyboardButton(text="❌ Возникла ошибка", callback_data="error")]
        ])

async def updated_master_menu(user_id):
    """Обновленное меню для мастеров с учетом админ-панели, если пользователь является администратором."""
    try:
        with SessionFactory() as session:
            master = session.query(Master).filter(Master.master_id == user_id).first()

            if master:  # если мастер существует
                # создаем базовое меню мастера
                menu_buttons = [
                    [InlineKeyboardButton(text="🟢 Активные записи", callback_data="active_bookings")],
                    [InlineKeyboardButton(text="📖 История записей", callback_data="booking_history")],
                    [InlineKeyboardButton(text="📋 Посмотреть прайс-лист", callback_data="get_price_list")],
                    [InlineKeyboardButton(text="🔲 Управление окошками", callback_data="windows")]
                ]

                # если мастер является администратором, добавляем кнопку админ-панели
                if user_id in ADMIN_ID:
                    menu_buttons.append([InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_panel")])

                # создаем и возвращаем InlineKeyboardMarkup с обновленным списком кнопок
                return InlineKeyboardMarkup(inline_keyboard=menu_buttons)
            else:  # если мастер был удален
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⚠️ Этот мастер был удалён", callback_data="main_menu")]
                ])
    except Exception as e:
        logging.error(f"Ошибка при проверке мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[  # если произошла ошибка
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
        [InlineKeyboardButton(text="➕ Добавить мастера", callback_data="add_master")],
        [InlineKeyboardButton(text="✏️ Редактировать мастера", callback_data="edit_master")],
        [InlineKeyboardButton(text="❌ Удалить мастера", callback_data="delete_master")],
        [InlineKeyboardButton(text="💼 Редактировать прайс-лист", callback_data="edit_price_list")],
        [InlineKeyboardButton(text="📜 История всех записей", callback_data="all_booking_history")],
        [InlineKeyboardButton(text="⬅️ Назад в главное меню", callback_data="main_menu")]
    ])
