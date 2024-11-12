# from aiogram import Router
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from datetime import datetime
#
# from Src.Handlers import Booking
# from database.database import SessionFactory
# # from database.repository import create_record
# from logger_config import logger
#
# router_booking = Router(name="booking")
#
# # Обработчик нажатия кнопки "Записаться"
# @router_booking.callback_query(lambda c: c.data == 'booking')
# async def process_callback_booking(callback_query: CallbackQuery):
#     await callback_query.answer()
#
#     master_menu = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Арина", callback_data="master_arina"),
#          InlineKeyboardButton(text="Маша", callback_data="master_masha")],
#         [InlineKeyboardButton(text="Назад", callback_data="main_menu", width=7)]
#     ])
#     await callback_query.message.edit_text("Выберите мастера:", reply_markup=master_menu)
#
#
# # Обработчик выбора мастера
# @router_booking.callback_query(lambda c: c.data.startswith('master_'))
# async def process_callback_master(callback_query: CallbackQuery):
#     master = callback_query.data.split('_')[1]
#     await callback_query.answer()
#
#     now = datetime.now()
#     month_str = now.strftime("%B %Y")
#     current_month = now.month
#
#     calendar_buttons = InlineKeyboardBuilder()
#     calendar_buttons.add(InlineKeyboardButton(text=month_str, callback_data="ignore", width=7))
#
#     week_days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
#     calendar_buttons.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in week_days])
#     week = []
#
#     for day in range(1, 32):
#         try:
#             date = datetime(now.year, current_month, day)
#             if date.month != current_month:
#                 break
#             date_str = date.strftime("%d")
#             callback_data = f'date_{master}_{date.strftime("%d.%m.%Y")}'
#
#             # Проверяем занятость даты в базе
#             with SessionFactory() as session:
#                 existing_record = session.query(Booking).filter_by(
#                     record_datetime=date.strftime('%Y-%m-%d %H:%M:%S')
#                 ).first()
#
#             if existing_record:
#                 week.append(InlineKeyboardButton(text=f"{date_str}❌", callback_data="ignore"))
#             else:
#                 week.append(InlineKeyboardButton(text=date_str, callback_data=callback_data))
#
#             if len(week) == 7:
#                 calendar_buttons.row(*week)
#                 week = []
#         except ValueError:
#             break
#     if week:
#         calendar_buttons.row(*week)
#
#     calendar_buttons.row(InlineKeyboardButton(text="Назад", callback_data="booking", width=7))
#     await callback_query.message.edit_text("Выберите дату:", reply_markup=calendar_buttons.as_markup())
#
#
# # Обработчик выбора времени
# @router_booking.callback_query(lambda c: c.data.startswith('time_'))
# async def process_callback_time(callback_query: CallbackQuery):
#     data = callback_query.data.split('_')
#     master, date, time = data[1], data[2], data[3]
#
#     await callback_query.answer()
#
#     # Проверяем занятость времени в базе
#     with SessionFactory() as session:
#         datetime_value = f"{date} {time}"
#         existing_record = session.query(Booking).filter_by(record_datetime=datetime_value).first()
#         if existing_record:
#             await callback_query.answer("Это время уже занято.", show_alert=True)
#             return
#
#         # Создаем запись без привязки к пользователю и мастеру
#         new_record = create_record(session=session, datetime_value=datetime_value)
#         if not new_record:
#             await callback_query.answer("Произошла ошибка при записи.", show_alert=True)
#             return
#
#     confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
#     ])
#     await callback_query.message.edit_text(
#         f"Запись подтверждена! Мастер: {master}, Дата: {date}, Время: {time}",
#         reply_markup=confirm_menu
#     )
