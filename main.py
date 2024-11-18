import asyncio
import logging

from Src.Handlers import get_handlers_router
from Src.Handlers.Booking.booking_handler import scheduler
from database.tables_creation import create_tables
from loader import bot, dp
from logger_config import logger

logging.basicConfig(level=logging.INFO)
#
# # Обработчик нажатия кнопки "Админ панель"
# @dp.callback_query(lambda c: c.data == "admin_panel")
# async def process_callback_admin_panel(callback_query: CallbackQuery):
#     user_id = callback_query.from_user.id
#     if user_id == ADMIN_ID:
#         await callback_query.answer()
#         await callback_query.message.edit_text("Административная панель:", reply_markup=admin_panel())
#         logger.info(f"Администратор {user_id} открыл административную панель.")
#     else:
#         await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)
#         logger.warning(f"Пользователь {user_id} попытался открыть административную панель.")
# #
# # Основное меню
# def main_menu(user_id):
#     buttons = [
#         [InlineKeyboardButton(text="Информация о мастерах", callback_data="masters"),
#          InlineKeyboardButton(text="Прайс лист", callback_data="price_list")],
#         [InlineKeyboardButton(text="Записаться", callback_data="booking", width=2)]
#     ]
#
#     # Проверка ID пользователя для отображения соответствующего меню
#     if user_id == ADMIN_ID:
#         buttons.append([InlineKeyboardButton(text="Админ панель", callback_data="admin_panel", width=2)])
#     elif str(user_id) in MASTER_IDS:
#         buttons = [
#             [InlineKeyboardButton(text="Активные записи", callback_data="active_master_bookings")],
#             [InlineKeyboardButton(text="История записей", callback_data="master_booking_history")],
#             [InlineKeyboardButton(text="Запросы на отмену", callback_data="cancel_requests")]
#         ]
#
#     return InlineKeyboardMarkup(inline_keyboard=buttons)
#
#
# def back_to_main_menu():
#     return InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Назад", callback_data="main_menu", width=7)]
#     ])
#
#
# # Обработчик нажатия кнопки "Начать"
# @dp.callback_query(lambda c: c.data == 'main_menu')
# async def process_callback_main_menu(callback_query: CallbackQuery):
#     user_id = callback_query.from_user.id
#     await callback_query.answer()
#     await callback_query.message.edit_text("Выберите действие:", reply_markup=main_menu(user_id))
#
#
# @dp.callback_query(lambda c: c.data == 'admin_panel')
# async def process_callback_admin_panel(callback_query: CallbackQuery):
#     user_id = callback_query.from_user.id
#     if user_id == ADMIN_ID:
#         await callback_query.answer()
#         await callback_query.message.edit_text("Административная панель:", reply_markup=admin_panel())
#     else:
#         await callback_query.answer("У вас нет доступа к этой функции.", show_alert=True)



#
# # Обработчик для отображения прайс-листа
# @dp.callback_query(lambda c: c.data == 'price_list')
# async def show_price_list(callback_query: CallbackQuery):
#     description = bookings.get('price_list_description', 'Описание прайс-листа пока не добавлено.')
#     photo_file_id = bookings.get('price_list_photo')
#     markup = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Назад", callback_data="back_to_main_menu")]
#     ])
#     await callback_query.answer()
#     if photo_file_id:
#         await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo_file_id, caption=description,
#                              reply_markup=markup)
#         await callback_query.message.delete()
#     else:
#         await bot.send_message(chat_id=callback_query.message.chat.id, text=description, reply_markup=markup)
#         await callback_query.message.delete()
#
#
# # Обработчик вызова редактирования прайс-листа
# @dp.callback_query(lambda c: c.data == 'edit_price_list')
# async def process_callback_edit_price_list(callback_query: CallbackQuery):
#     await callback_query.answer()
#     await callback_query.message.edit_text("Введите описание прайс-листа и загрузите фото (если требуется).")
#     bookings['awaiting_price_list_description'] = True  # Устанавливаем флаг ожидания описания
#
#
# # Обработчик для добавления прайс-листа без команды
# @dp.message(lambda message: bookings.get('awaiting_price_list_description'))
# async def add_price_list_info(message: Message):
#     try:
#         description = message.text
#         bookings['price_list_description'] = description
#         bookings.pop('awaiting_price_list_description', None)  # Убираем флаг ожидания описания
#         bookings['awaiting_price_list_photo'] = True  # Устанавливаем флаг ожидания фото
#         await message.answer("Описание прайс-листа обновлено. Теперь загрузите фото.")
#     except Exception as e:
#         await message.answer("Ошибка при добавлении прайс-листа. Попробуйте снова.")
#
#
# # Обработчик для загрузки фото прайс-листа
# @dp.message(lambda message: message.photo and bookings.get('awaiting_price_list_photo'))
# async def handle_price_list_photo(message: Message):
#     if bookings.get('awaiting_price_list_photo'):
#         photo_file_id = message.photo[-1].file_id
#         bookings['price_list_photo'] = photo_file_id
#         bookings.pop('awaiting_price_list_photo', None)  # Убираем флаг ожидания фото
#         await message.answer("Фото прайс-листа обновлено.")
#     else:
#         await message.answer("Пожалуйста, сначала добавьте описание прайс-листа.")
#
#
# # Обработчик для отображения прайс-листа
# @dp.callback_query(lambda c: c.data == 'price_list')
# async def show_price_list(callback_query: CallbackQuery):
#     description = bookings.get('price_list_description', 'Описание прайс-листа пока не добавлено.')
#     photo_file_id = bookings.get('price_list_photo')
#     markup = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Назад", callback_data="back_to_main_menu")]
#     ])
#     await callback_query.answer()
#     if photo_file_id:
#         await bot.send_photo(chat_id=callback_query.message.chat.id, photo=photo_file_id, caption=description,
#                              reply_markup=markup)
#         await callback_query.message.delete()
#     else:
#         await bot.send_message(chat_id=callback_query.message.chat.id, text=description, reply_markup=markup)
#         await callback_query.message.delete()
#
#
# # Обработчик нажатия кнопки "Назад"
# @dp.callback_query(lambda c: c.data == 'back_to_main_menu')
# async def process_callback_back_to_main_menu(callback_query: CallbackQuery):
#     user_id = callback_query.from_user.id
#     await callback_query.answer()
#     await callback_query.message.delete()
#     await bot.send_message(callback_query.message.chat.id, "Выберите действие:", reply_markup=main_menu(user_id))
#
#
# # Удаление мастера
# @dp.callback_query(lambda c: c.data == 'delete_master')
# async def process_delete_master(callback_query: CallbackQuery):
#     await callback_query.answer()
#     if masters:
#         master_list = "\n".join([f"{m_id}: {m_info['name']}" for m_id, m_info in masters.items()])
#         await callback_query.message.edit_text(
#             f"Выберите мастера для удаления:\n{master_list}\nОтправьте ID мастера командой /delete_master_info")
#     else:
#         await callback_query.message.edit_text("Нет доступных мастеров для удаления.")
#
#
# @dp.message(Command("delete_master_info"))
# async def delete_master_info(message: Message):
#     try:
#         master_id = message.text.strip()
#         if master_id in masters:
#             del masters[master_id]
#             MASTER_IDS.discard(master_id)
#             await message.answer(f"Мастер с ID {master_id} удален.")
#         else:
#             await message.answer("Мастер с указанным ID не найден.")
#     except Exception as e:
#         await message.answer("Ошибка при удалении мастера. Попробуйте снова.")
#

# # Команда для получения ID пользователем
# @dp.message(Command("getid"))
# async def send_user_id(message: Message):
#     user_id = message.from_user.id
#     await message.answer(f"Ваш ID: {user_id}")
#
#
# # Сбор запросов пользователей на получение их ID
# @dp.message(Command("getid"))
# async def send_user_id(message: Message):
#     user_id = message.from_user.id
#     users.add(user_id)
#     await message.answer(f"Ваш ID: {user_id} был отправлен администратору.")
#
#
# # Команда для администратора для получения списка всех запросов ID
# @dp.message(Command("showids"))
# async def show_all_user_ids(message: Message):
#     if message.from_user.id == ADMIN_ID:
#         if users:
#             ids_list = "\n".join(str(user_id) for user_id in users)
#             await message.answer(f"ID пользователей:\n{ids_list}")
#         else:
#             await message.answer("Нет запросов на получение ID.")
#     else:
#         await message.answer("У вас нет доступа к этой функции.")
#
#
#
# # Обработчик выбора времени
# @dp.callback_query(lambda c: c.data.startswith('time_'))
# async def process_callback_time(callback_query: CallbackQuery):
#     data = callback_query.data.split('_')
#     master, date, time = data[1], data[2], data[3]
#     user_id = callback_query.from_user.id
#
#     if user_id in users:
#         await callback_query.answer("Вы уже осуществили запись.", show_alert=True)
#         return
#
#     await callback_query.answer()
#
#     # Записываем данные о занятом времени
#     callback_data = f'time_{master}_{date}_{time}'
#     bookings[callback_data] = user_id
#     users.add(user_id)
#
#     # Сообщение о подтверждении записи с кнопкой "Главное меню"
#     confirm_menu = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]
#     ])
#     await callback_query.message.edit_text(f"Запись подтверждена! Мастер: {master}, Дата: {date}, Время: {time}",
#                                            reply_markup=confirm_menu)
#
#
# # Обработчик нажатия кнопки "Активные записи"
# @dp.callback_query(lambda c: c.data == 'active_bookings')
# async def show_active_bookings(callback_query: CallbackQuery):
#     active_bookings = [booking for booking in bookings.items() if booking[1] in users]
#     if active_bookings:
#         for callback_data, user_id in active_bookings:
#             keyboard = InlineKeyboardMarkup(inline_keyboard=[
#                 [InlineKeyboardButton(text="Редактировать", callback_data=f"edit_{callback_data}"),
#                  InlineKeyboardButton(text="Отменить", callback_data=f"cancel_{callback_data}")]
#             ])
#             await callback_query.message.answer(f"Активная запись: {callback_data}", reply_markup=keyboard)
#     else:
#         await callback_query.message.answer("Нет активных записей.")
#     await callback_query.answer()
#
#
# # Обработчик нажатия кнопки "Неактивные записи"
# @dp.callback_query(lambda c: c.data == 'inactive_bookings')
# async def show_inactive_bookings(callback_query: CallbackQuery):
#     inactive_bookings = [booking for booking in bookings.items() if booking[1] not in users]
#     if inactive_bookings:
#         for callback_data, user_id in inactive_bookings:
#             await callback_query.message.answer(f"Неактивная запись: {callback_data}")
#     else:
#         await callback_query.message.answer("Нет неактивных записей.")
#     await callback_query.answer()
#
#
# # Обработчик нажатия кнопки "Отменить"
# @dp.callback_query(lambda c: c.data.startswith('cancel_'))
# async def cancel_booking(callback_query: CallbackQuery):
#     callback_data = callback_query.data.split('cancel_')[1]
#     if callback_data in bookings:
#         del bookings[callback_data]
#         users.remove(callback_data)
#         await callback_query.answer("Запись отменена.")
#         await callback_query.message.edit_text("Запись отменена.")
#     else:
#         await callback_query.answer("Ошибка: запись не найдена.", show_alert=True)
#

async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    logger.debug("Bot session stopped")

async def on_startup():
    create_tables()
    dp.include_router(get_handlers_router())
    logger.debug("Bot session started")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запуск процесса поллинга новых апдейтов
    await dp.start_polling(bot)

if __name__ == '__main__':
    scheduler.start()
    asyncio.run(main())  # Это важно!
