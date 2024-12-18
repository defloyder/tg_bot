from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from logger_config import logger

router_chat = Router(name="chat")


class ChatStates(StatesGroup):
    user_chatting = State()
    master_chatting = State()


@router_chat.callback_query(lambda c: c.data.startswith("write_to_master_"))
async def initiate_chat_with_master(callback_query: CallbackQuery, state: FSMContext):
    master_id = callback_query.data.split("_")[-1]

    try:
        await callback_query.message.answer(
            "Вы можете написать сообщение мастеру. После каждого сообщения вы сможете завершить диалог.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Завершить диалог", callback_data="end_user_chat")]]
            )
        )

        await state.set_state(ChatStates.user_chatting)
        await state.update_data(chat_with_master=master_id)

    except Exception as e:
        logger.error(f"Ошибка при начале чата с мастером {master_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)

@router_chat.message(ChatStates.user_chatting)
async def user_send_message(message: Message, state: FSMContext):
    data = await state.get_data()
    master_id = data.get("chat_with_master")

    if not master_id:
        await message.answer("Произошла ошибка. Попробуйте снова.")
        return

    try:
        await message.bot.send_message(
            master_id,
            f"Сообщение от пользователя {message.from_user.full_name}:\n{message.text}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать диалог", callback_data=f"start_master_chat_{message.from_user.id}")]]
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения мастеру {master_id}: {e}")
        await message.answer("Не удалось отправить сообщение мастеру. Попробуйте позже.")


@router_chat.callback_query(lambda c: c.data == "end_user_chat")
async def end_user_chat(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("Диалог завершён. Спасибо за использование сервиса!")


@router_chat.callback_query(lambda c: c.data.startswith("start_master_chat_"))
async def master_initiate_chat(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.data.split("_")[-1]

    try:
        await callback_query.message.answer(
            "Вы можете ответить пользователю. После каждого сообщения вы сможете завершить диалог.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Завершить диалог", callback_data="end_master_chat")]]
            )
        )

        await state.set_state(ChatStates.master_chatting)
        await state.update_data(chat_with_user=user_id)

    except Exception as e:
        logger.error(f"Ошибка при начале чата с пользователем {user_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)


@router_chat.message(ChatStates.master_chatting)
async def master_send_message(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("chat_with_user")

    if not user_id:
        await message.answer("Произошла ошибка. Попробуйте снова.")
        return

    try:
        await message.bot.send_message(
            user_id,
            f"Сообщение от мастера {message.from_user.full_name}:\n{message.text}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Начать диалог", callback_data=f"start_master_chat_{message.chat.id}")]]
            )
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        await message.answer("Не удалось отправить сообщение пользователю. Попробуйте позже.")


@router_chat.callback_query(lambda c: c.data == "end_master_chat")
async def end_master_chat(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("Диалог завершён. Спасибо за использование сервиса!")
