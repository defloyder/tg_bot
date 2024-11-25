from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from database import Master
from database.database import SessionFactory
import logging

ADMIN_ID = [475953677, 962757762]

async def main_menu(user_id):
    try:
        with SessionFactory() as session:
            master_exists = session.query(Master).filter(Master.master_id == user_id).first()

            if master_exists:
                return master_menu()

        buttons = [
            [InlineKeyboardButton(text="Информация о мастерах", callback_data="masters"),
             InlineKeyboardButton(text="Прайс лист", callback_data="get_price_list")],
            [InlineKeyboardButton(text="Записаться", callback_data="booking")],
            [InlineKeyboardButton(text="Мои записи", callback_data="my_bookings")]
        ]


        if user_id in ADMIN_ID:
            buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin_panel")])

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    except Exception as e:
        logging.error(f"Ошибка при извлечении мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Возникла ошибка", callback_data="error")]])

def master_menu():
    buttons = [
        [InlineKeyboardButton(text="Активные записи", callback_data="active_bookings")],
        [InlineKeyboardButton(text="История записей", callback_data="booking_history")],
        [InlineKeyboardButton(text="Прайс лист", callback_data="get_price_list")],
        [InlineKeyboardButton(text="Окошки", callback_data="windows")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def updated_master_menu(user_id):
    try:
        with SessionFactory() as session:
            master_exists = session.query(Master).filter(Master.master_id == user_id).first()

            if master_exists:
                return master_menu()
            else:
                return InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Этот мастер был удален", callback_data="main_menu")]
                ])
    except Exception as e:
        logging.error(f"Ошибка при проверке мастера из базы данных: {e}")
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Возникла ошибка", callback_data="error")]])

def back_to_master_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад", callback_data="master_menu")
    ]])

def back_to_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Назад", callback_data="main_menu")
    ]])

def my_bookings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Активные записи", callback_data="active_bookings")
    ], [
        InlineKeyboardButton(text="История записей", callback_data="booking_history")
    ], [
        InlineKeyboardButton(text="Назад", callback_data="main_menu")
    ]])

def admin_panel():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Добавить мастера", callback_data="add_master")
    ], [
        InlineKeyboardButton(text="Редактировать мастера", callback_data="edit_master")
    ], [
        InlineKeyboardButton(text="Удалить мастера", callback_data="delete_master")
    ], [
        InlineKeyboardButton(text="Редактировать прайс-лист", callback_data="edit_price_list")
    ], [
        InlineKeyboardButton(text="История записей", callback_data="all_booking_history")
    ], [
        InlineKeyboardButton(text="Назад", callback_data="main_menu")
    ]])
