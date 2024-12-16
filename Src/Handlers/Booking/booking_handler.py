import re
from datetime import datetime, timedelta
import time
from aiogram import Router, Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import SQLAlchemyError
from yookassa import Payment
from Src.Handlers.Booking.service import generate_calendar
from Src.Handlers.MyBookings.my_bookings_handler import back_to_my_bookings_menu
from database import Booking, Master
from database.database import SessionFactory
from database.models import MasterSchedule, UserSchedule
from database.repository import create_booking
from logger_config import logger
from menu import main_menu
from yookassa import Configuration

import aioredis

redis_client = aioredis.from_url("redis://localhost", decode_responses=True)


scheduler = AsyncIOScheduler()
blocked_times = {}


Configuration.account_id = "497898"  # Замените на ваш shopId
Configuration.secret_key = "live_b1msS56RfztJrOmB-3K2ii9gMUTp8TRhbS2FRe6hmtU"  # Замените на ваш secret key
router_booking = Router(name="booking")
ADMIN_ID = [475953677, 962757762]
TIME_WINDOW = 10
MAX_CLICKS = 5


# Код для работы с Redis
async def is_flood(user_id: int, max_clicks: int, time_window: int) -> bool:
    """
    Проверка на флуда через Redis.
    :param user_id: ID пользователя
    :param max_clicks: Максимальное количество нажатий в пределах time_window
    :param time_window: Время в секундах, за которое учитываются нажатия
    :return: True, если количество нажатий превышает лимит, иначе False
    """
    key = f"flood:{user_id}"

    current_clicks = await redis_client.incr(key)

    if current_clicks == 1:
        await redis_client.expire(key, time_window)

    if current_clicks > max_clicks:
        return True

    return False



@router_booking.callback_query(lambda c: c.data == 'booking')
async def process_callback_booking(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return

    logger.info("Обработчик нажатия кнопки 'Записаться' запущен.")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            masters = session.query(Master).all()

        if not masters:
            await callback_query.message.edit_text("⚠️ *Мастера не найдены. Попробуйте позже.*")
            return

        master_menu = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"⚜️ {master.master_name}",
                                      callback_data=f"booking_master_{master.master_id}")]
                for master in masters
            ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]
        )

        await callback_query.message.edit_text("👨‍🔧 Выберите мастера для записи:", reply_markup=master_menu)
        logger.debug("Отправлено динамическое меню с выбором мастеров.")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка при загрузке списка мастеров: {e}")
        await callback_query.message.edit_text("❌ Произошла ошибка. Попробуйте позже.")

@router_booking.callback_query(lambda c: c.data.startswith('booking_master_'))
async def process_callback_master(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    try:
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 3 or data_parts[0] != "booking" or data_parts[1] != "master":
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("❌ Некорректные данные. Попробуйте снова.", show_alert=True)
            return

        master_id = data_parts[2]

        logger.debug(f"Пользователь выбрал мастера с ID: {master_id}")

        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "❌ Не удалось загрузить календарь. Попробуйте позже.",
                reply_markup=None
            )
            return

        await callback_query.message.edit_text("📅 Выберите дату для записи:", reply_markup=calendar_markup)
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")

    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору даты для мастера {callback_query.data}: {e}")
        await callback_query.answer("❌ Произошла ошибка при возврате к выбору даты.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    try:
        data = callback_query.data.split('_')
        master_id, date = data[1], data[2]
        logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
        await callback_query.answer()

        start_time = 10
        end_time = 22
        time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]

        with SessionFactory() as session:
            selected_date = datetime.strptime(date, '%Y-%m-%d').date()

            user_schedule_entry = session.query(UserSchedule).filter(
                UserSchedule.user_id == master_id,
                UserSchedule.date == selected_date
            ).first()

            day_blocked = user_schedule_entry and user_schedule_entry.is_blocked

            blocked_times = set()
            if not day_blocked:
                master_schedule = session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.date == selected_date,
                    MasterSchedule.is_blocked == True
                ).all()

                for entry in master_schedule:
                    blocked_hour = entry.start_time.hour
                    blocked_times.add(f"{blocked_hour:02}:00")

            time_buttons = []
            row = []
            for time in time_slots:
                if day_blocked or time in blocked_times:
                    row.append(InlineKeyboardButton(text=f"❌ {time}", callback_data="ignore"))
                else:
                    row.append(
                        InlineKeyboardButton(text=f"🕒 {time}",
                                             callback_data=f"time_{master_id}_{selected_date}_{time}:00"))

                if len(row) == 3:
                    time_buttons.append(row)
                    row = []

            if row:
                time_buttons.append(row)

            time_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"master_{master_id}")])

            await callback_query.message.edit_text(
                "⏰ Выберите доступное время:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=time_buttons)
            )
            logger.debug(f"Доступные временные слоты отправлены пользователю.")
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("❌ Произошла ошибка при обработке времени.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    pattern = r'time_(\d+)_(\d{4}-\d{2}-\d{2})_(\d{2}):(\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, hour, minute = match.groups()
    selected_time = f"{hour}:{minute}"
    user_id = callback_query.from_user.id

    logger.info(f"Пользователь {user_id} выбрал время {selected_time} для мастера {master_id} на дату {date}")

    try:
        with SessionFactory() as session:
            blocked_slots = set(
                entry.start_time.strftime('%H:%M') for entry in session.query(MasterSchedule).filter(
                    MasterSchedule.master_id == master_id,
                    MasterSchedule.date == datetime.strptime(date, '%Y-%m-%d').date(),  # Используем точную дату
                    MasterSchedule.is_blocked == True
                ).all()
            )

            if selected_time in blocked_slots:
                await callback_query.message.edit_text(
                    f"К сожалению, выбранное время {selected_time} заблокировано. Пожалуйста, выберите другое время.",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=f"date_{master_id}_{date}")]]
                    )
                )
                logger.info(f"Пользователь {user_id} попытался выбрать заблокированное время {selected_time}.")
                return

            active_booking = session.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.status == "new",
                Booking.booking_datetime > datetime.now()
            ).first()

            if active_booking:
                time_diff = datetime.now() - active_booking.booking_datetime
                if time_diff.days < 7:
                    booking_datetime = active_booking.booking_datetime.strftime('%d.%m.%Y %H:%M')
                    await callback_query.message.edit_text(
                        f"У вас уже есть активная запись на {booking_datetime}. "
                        f"Вы сможете записаться снова через {7 - time_diff.days} дней.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="Главное меню", callback_data="main_menu")]]
                        )
                    )
                    logger.info(f"Пользователь {user_id} пытался записаться ранее, чем через 7 дней.")
                    return

    except Exception as e:
        logger.error(f"Ошибка при проверке активной записи для пользователя {user_id}: {e}")
        await callback_query.answer("Произошла ошибка при проверке активной записи. Попробуйте позже.", show_alert=True)
        return

    minute_buttons = InlineKeyboardMarkup(
        inline_keyboard=[  # Кнопки минут
            [
                InlineKeyboardButton(text="00 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_00"),
                InlineKeyboardButton(text="15 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_15"),
                InlineKeyboardButton(text="30 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_30"),
                InlineKeyboardButton(text="45 минут", callback_data=f"minute_{master_id}_{date}_{hour}_{minute}_45"),
            ],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"date_{master_id}_{date}")]
        ]
    )

    logger.info(f"Отправлены кнопки выбора минут пользователю {user_id}. Выбранное время: {selected_time}.")

    await callback_query.message.edit_text(
        f"Вы выбрали <b>{selected_time}</b>. Давайте теперь уточним более точное время😽😻:",
        reply_markup=minute_buttons
    )


@router_booking.callback_query(lambda c: c.data.startswith('minute_'))
async def process_callback_minute(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    pattern = r'minute_(\d+)_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})_(\d{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, hour, minute, selected_minute = match.groups()
    user_id = callback_query.from_user.id

    selected_time = datetime.strptime(f"{hour}:{minute}", '%H:%M')
    selected_minute = int(selected_minute)  # Выбранные минуты
    final_time = selected_time + timedelta(minutes=selected_minute)

    final_time_str = final_time.strftime('%H:%M')

    logger.info(f"Пользователь {user_id} выбрал время {final_time_str} для мастера {master_id} на дату {date}.")

    try:
        with SessionFactory() as session:
            active_booking = session.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.status == "new",
                Booking.booking_datetime > datetime.now()
            ).first()

            if active_booking:
                time_diff = datetime.now() - active_booking.booking_datetime
                if time_diff.days < 7:
                    booking_datetime = active_booking.booking_datetime.strftime('%d.%m.%Y %H:%M')
                    await callback_query.message.edit_text(
                        f"У вас уже есть активная запись на <b>{booking_datetime}</b>. "
                        f"Вы сможете записаться снова через {7 - time_diff.days} дней.",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="🏚️ Главное меню", callback_data="main_menu")]]
                        )
                    )
                    logger.info(f"Пользователь {user_id} пытался записаться ранее, чем через 7 дней.")
                    return

    except Exception as e:
        logger.error(f"Ошибка при проверке активной записи для пользователя {user_id}: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте позже.", show_alert=True)
        return

    confirm_buttons = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="Оплатить предоплату", callback_data=f"confirm_{master_id}_{date}_{final_time_str}"),
            InlineKeyboardButton(text="Отменить запись", callback_data="cancel_booking")
        ]]
    )

    logger.info(f"Отправлены кнопки подтверждения записи пользователю {user_id}. Время: {final_time_str}.")

    await callback_query.message.edit_text(
        f"Запись будет создана на  <b>{date}</b> <b>{final_time_str}</b>.💫 Для подтверждения записи просим внести предоплату!💖🦄",
        reply_markup=confirm_buttons
    )


@router_booking.callback_query(lambda c: c.data.startswith('confirm_') and not c.data.startswith('confirm_delete_'))
async def process_confirm_time(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger.info(f"Пользователь {user_id} начал подтверждение записи: {callback_query.data}")

    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        logger.warning(f"Флуд-атака от пользователя {user_id}: превышено количество нажатий.")
        await callback_query.answer("❌ Не спешите, немного подождите и попробуйте еще раз нажать на нужную кнопку😽",
                                    show_alert=True)
        return

    pattern = r'confirm_(\d+)_([\d]{4}-[\d]{2}-[\d]{2})_([\d]{2}:[\d]{2})'
    match = re.match(pattern, callback_query.data)

    if not match:
        logger.error(f"Некорректные данные callback: {callback_query.data}")
        await callback_query.answer("Ошибка при обработке данных. Попробуйте снова.", show_alert=True)
        return

    master_id, date, time = match.groups()
    logger.info(f"Извлечены данные: мастер {master_id}, дата {date}, время {time}")

    try:
        booking_datetime = datetime.strptime(f"{date} {time}", '%Y-%m-%d %H:%M')
    except ValueError as e:
        logger.error(f"Ошибка преобразования даты/времени: {date} {time} — {e}")
        await callback_query.answer("Некорректная дата или время. Попробуйте снова.", show_alert=True)
        return

    logger.info(f"Дата и время успешно преобразованы: {booking_datetime}")

    try:
        with SessionFactory() as session:
            overlapping_booking = session.query(Booking).filter(
                Booking.master_id == master_id,
                Booking.status == "new",
                Booking.booking_datetime <= booking_datetime,
                (Booking.booking_datetime + timedelta(hours=4)) > booking_datetime
            ).first()

            if overlapping_booking:
                logger.warning(f"Попытка записи на занятое время {booking_datetime} пользователем {user_id}")
                await callback_query.answer(
                    "⛔ Выбранное время уже занято. Пожалуйста, выберите другое.",
                    show_alert=True
                )
                return

            logger.info(f"Время {booking_datetime} доступно для записи.")

            try:
                logger.info(f"Создание платежа для пользователя {user_id}")
                payment = Payment.create({
                    "amount": {"value": "500.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "return_url": f"https://t.me/pink_reserve_bot?payment_id={{payment.id}}"
                    },
                    "capture": True,
                    "description": f"Оплата записи на {date} {time}",
                    "receipt": {
                        "customer": {
                            "full_name": callback_query.from_user.full_name or "Имя пользователя",
                            "email": "chigirevaarina@gmail.com",
                            "phone": "79296430546"
                        },
                        "items": [
                            {
                                "description": f"Услуга записи на {date} {time}",
                                "quantity": "1.00",
                                "amount": {"value": "500.00", "currency": "RUB"},
                                "vat_code": "1",
                                "payment_mode": "full_payment",
                                "payment_subject": "service"
                            }
                        ]
                    }
                })
                confirmation_url = payment.confirmation.confirmation_url
                payment_id = payment.id  # Сохраняем ID платежа
                logger.info(f"Платеж создан успешно: {payment_id} для пользователя {user_id}")

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подтвердить оплату💖", callback_data=f"paid_{payment_id}")]
                ])

                await callback_query.message.edit_text(
                    f"Для подтверждения записи просьба внести предоплату через ЮКассу🦄💖\n\n"
                    f"[Оплата предоплаты⚜️]({confirmation_url})",
                    parse_mode="Markdown",
                    reply_markup=keyboard  # Передаем клавиатуру с кнопкой
                )
                logger.info(f"Сообщение с оплатой отправлено пользователю {user_id}.")
                return

            except Exception as e:
                logger.error(f"Ошибка при создании платежа через Юкассу для пользователя {user_id}: {e}")
                await callback_query.answer("❌ Произошла ошибка при создании платежа. Попробуйте позже.",
                                            show_alert=True)
                return

    except Exception as e:
        logger.error(f"Ошибка при подтверждении записи для пользователя {user_id}: {e}")
        await callback_query.answer("❌ Произошла ошибка при записи. Попробуйте позже.", show_alert=True)

@router_booking.callback_query(lambda c: c.data.startswith('paid_'))
async def process_payment_confirmation(callback_query: CallbackQuery):
    payment_id = callback_query.data.split('_')[1]
    user_id = callback_query.from_user.id

    logger.info(f"Пользователь {user_id} нажал кнопку 'Предоплата внесена' для payment_id {payment_id}")

    try:
        payment = Payment.find_one(payment_id)
        payment_status = payment.status

        if payment_status == 'succeeded':
            with SessionFactory() as session:
                master_id = session.query(Booking.master_id).filter_by(payment_id=payment_id).scalar()
                booking_datetime = session.query(Booking.booking_datetime).filter_by(payment_id=payment_id).scalar()

                if not master_id or not booking_datetime:
                    logger.error(f"Не удалось найти данные о мастере или дате для payment_id {payment_id}")
                    await callback_query.message.edit_text("❌ Произошла ошибка. Пожалуйста, обратитесь в поддержку.")
                    return

                new_booking = Booking(
                    booking_datetime=booking_datetime,
                    status="new",
                    user_id=user_id,
                    master_id=master_id,
                    payment_id=payment_id
                )
                session.add(new_booking)
                session.commit()
                logger.info(f"Запись успешно создана для пользователя {user_id}")

                await callback_query.message.edit_text(
                    f"✅ Запись подтверждена!\n\n"
                    f"📅 Дата: {new_booking.booking_datetime.strftime('%Y-%m-%d')}\n"
                    f"⏰ Время: {new_booking.booking_datetime.strftime('%H:%M')}\n"
                    f"⛩️ Мы находимся по адресу: г. Москва, метро Владыкино, ул. Ботаническая 14а",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
                            [InlineKeyboardButton(text="💬 Написать мастеру", callback_data=f"write_to_master_{new_booking.master_id}")]
                        ]
                    )
                )
        else:
            logger.warning(f"Платеж с payment_id {payment_id} не подтвержден.")
            confirmation_url = payment.confirmation.confirmation_url
            await callback_query.message.edit_text(
                f"Для подтверждения записи просьба внести предоплату через ЮКассу🦄💖\n\n"
                f"[Ссылка для оплаты⚜️]({confirmation_url})\n\n"
                "❌ Платеж не был подтвержден.\nПожалуйста, попробуйте оплатить снова.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Подтвердить оплату💖", callback_data=f"paid_{payment_id}")]
                    ]
                )
            )

    except Exception as e:
        logger.error(f"Ошибка при проверке статуса платежа для {payment_id}: {e}")
        await callback_query.message.edit_text("❌ Произошла ошибка при обработке платежа.")


async def block_time_slots(session, master_id, booking_datetime):
    """Блокировка выбранного времени и следующего часа."""
    slots_to_block = [booking_datetime, booking_datetime + timedelta(hours=1)]

    for time_slot in slots_to_block:
        day_of_week = time_slot.weekday()

        existing_entry = session.query(MasterSchedule).filter(
            MasterSchedule.master_id == master_id,
            MasterSchedule.date == time_slot.date(),
            MasterSchedule.start_time == time_slot.time(),
        ).first()

        if not existing_entry:
            new_schedule = MasterSchedule(
                master_id=master_id,
                day_of_week=day_of_week,
                date=time_slot.date(),
                start_time=time_slot.time(),
                is_blocked=True
            )
            session.add(new_schedule)
            logger.info(f"Заблокирован слот: {time_slot} для мастера {master_id}.")
    session.commit()

def unblock_time_slot(session, master_id, booking_datetime):
    """
    Снимает блокировку временного слота.
    """
    try:
        blocked_slot = session.query(MasterSchedule).filter(
            MasterSchedule.master_id == master_id,
            MasterSchedule.date == booking_datetime.date(),
            MasterSchedule.start_time == booking_datetime.time(),
            MasterSchedule.is_blocked == True
        ).first()

        if blocked_slot:
            blocked_slot.is_blocked = False
            session.commit()
            logger.info(f"Временной слот {booking_datetime} разблокирован для мастера ID {master_id}.")
    except Exception as e:
        logger.error(f"Ошибка при разблокировке временного слота: {e}")


async def handle_delete_booking(callback_query, master_id):
    logger.info(f"Пользователь запросил удаление записи для мастера {master_id}.")
    await callback_query.answer("Запрос на удаление обработки...")


@router_booking.callback_query(lambda c: c.data == 'cancel_booking')
async def process_cancel_booking(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    await callback_query.message.edit_text(
        "❌ Создание записи отменено. Вы возвращены в главное меню.",
        reply_markup=await main_menu(user_id)
    )


@router_booking.callback_query(lambda c: c.data.startswith('master_'))
async def process_callback_master_return(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    logger.debug(f"Получен callback_data: {callback_query.data}")
    try:
        data_parts = callback_query.data.split('_')
        if len(data_parts) != 2:
            logger.error(f"Некорректный формат callback_data: {callback_query.data}")
            await callback_query.answer("Некорректные данные. Попробуйте снова.", show_alert=True)
            return

        master_id = data_parts[1]
        logger.debug(f"Пользователь вернулся к выбору даты для мастера с ID: {master_id}")

        calendar_markup = await generate_calendar(master_id)
        if not calendar_markup:
            logger.error(f"Не удалось сгенерировать календарь для мастера {master_id}")
            await callback_query.message.edit_text(
                "Не удалось загрузить календарь. Попробуйте позже.",
                reply_markup=None
            )
            return

        await callback_query.message.edit_text(
            "Выберите дату для записи:",
            reply_markup=calendar_markup
        )
        logger.debug(f"Календарь для мастера {master_id} успешно отправлен.")

    except Exception as e:
        logger.error(f"Ошибка при возврате к выбору даты для мастера {callback_query.data}: {e}")
        await callback_query.answer("Произошла ошибка при возврате к выбору даты.", show_alert=True)


@router_booking.callback_query(lambda c: c.data.startswith('edit_booking_'))
async def process_edit_booking(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    """Обработчик для кнопки 'Редактировать' записи, где мастер остаётся прежним, только дата и время меняются."""
    try:
        booking_id = int(callback_query.data.split("_")[-1])
    except ValueError:
        logger.error(f"Некорректные данные в callback: {callback_query.data}")
        await callback_query.answer("Ошибка обработки данных. Попробуйте снова.", show_alert=True)
        return

    try:
        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                await callback_query.message.edit_text("Запись не найдена.", reply_markup=back_to_my_bookings_menu())
                return

            master_name = session.query(Master.master_name).filter(Master.master_id == booking.master_id).first()
            master_name = master_name[0] if master_name else "Неизвестно"

            old_booking_datetime = booking.booking_datetime.strftime('%d.%m.%Y %H:%M')

            calendar_markup = await generate_calendar(booking.master_id)
            await callback_query.message.edit_text(
                f"Вы выбрали мастера: {master_name}, дата: {old_booking_datetime}\nВыберите новую дату для редактирования записи.",
                reply_markup=calendar_markup)

    except Exception as e:
        logger.error(f"Ошибка при редактировании записи: {e}")
        await callback_query.message.edit_text("Произошла ошибка при редактировании записи. Попробуйте позже.",
                                               reply_markup=back_to_my_bookings_menu())


@router_booking.callback_query(lambda c: c.data.startswith('cancel_booking_'))
async def cancel_booking(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer(
            "❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
            show_alert=True
        )
        return

    try:
        pattern = r'cancel_booking_(\d+)'
        match = re.match(pattern, callback_query.data)

        if not match:
            logger.error(f"Некорректные данные callback: {callback_query.data}")
            await callback_query.answer("❌ Ошибка обработки данных. Попробуйте снова.", show_alert=True)
            return

        booking_id = int(match.group(1))

        with SessionFactory() as session:
            booking = session.query(Booking).filter(Booking.booking_id == booking_id).first()

            if not booking:
                logger.warning(f"Попытка отменить несуществующую запись: ID {booking_id}")
                await callback_query.answer("⚠️ Запись не найдена.", show_alert=True)
                return

            if booking.status == "cancelled":
                logger.info(f"Запись ID {booking_id} уже отменена.")
                await callback_query.answer("⚠️ Запись уже отменена.", show_alert=True)
                return

            master_id = booking.master_id
            booking_datetime = booking.booking_datetime

            session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id,
                MasterSchedule.date == booking_datetime.date(),
                MasterSchedule.start_time.in_([
                    booking_datetime.time(),
                    (booking_datetime + timedelta(hours=1)).time()
                ])
            ).delete()

            booking.status = "cancelled"
            session.commit()

            logger.info(f"Запись ID {booking_id} успешно отменена пользователем ID {user_id}.")

            await callback_query.message.edit_text(
                "✅ Ваша запись была успешно отменена.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
                )
            )

            master = session.query(Master).filter(Master.master_id == master_id).first()
            if master:
                try:
                    await callback_query.bot.send_message(
                        master.master_id,
                        f"📅 Запись пользователя {callback_query.from_user.full_name} "
                        f"на {booking_datetime.strftime('%d.%m.%Y %H:%M')} была отменена.",
                    )
                    logger.info(f"Уведомление отправлено мастеру ID {master.master_id}.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления мастеру {master.master_id}: {e}")

    except SQLAlchemyError as e:
        logger.error(f"Ошибка базы данных при отмене записи: {e}")
        await callback_query.answer("❌ Ошибка при отмене записи. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка при отмене записи: {e}")
        await callback_query.answer("⚠️ Произошла ошибка. Попробуйте снова.", show_alert=True)


async def generate_time_buttons(session, master_id, date):
    """
    Генерирует кнопки для выбора времени на заданную дату.
    """
    start_time = 10
    end_time = 22
    time_slots = [f"{hour:02}:00" for hour in range(start_time, end_time + 1)]

    blocked_times = set(
        entry.start_time.strftime('%H:%M') for entry in session.query(MasterSchedule).filter(
            MasterSchedule.master_id == master_id,
            MasterSchedule.date == date,
            MasterSchedule.is_blocked == True
        ).all()
    )

    time_buttons = []
    row = []
    for time in time_slots:
        if time in blocked_times:
            row.append(InlineKeyboardButton(text=f"❌ {time}", callback_data="ignore"))
        else:
            row.append(
                InlineKeyboardButton(text=f"🕒 {time}",
                                     callback_data=f"time_{master_id}_{date}_{time}:00")
            )

        if len(row) == 3:
            time_buttons.append(row)
            row = []

    if row:
        time_buttons.append(row)

    time_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"master_{master_id}")])
    return InlineKeyboardMarkup(inline_keyboard=time_buttons)


async def send_booking_reminder(bot: Bot, user_id: int, master_name: str, booking_time: datetime):
    try:
        reminder_text = (
            f"⏰ Напоминание: У вас запись к мастеру {master_name} "
            f"на {booking_time.strftime('%d.%m.%Y %H:%M')}. Не забудьте прийти вовремя! "
            "🙏 Будем рады вас увидеть!"
            "⛩️ Мы находимся по адресу: г. Москва, метро Владыкино, ул. Ботаническая 14а"
        )
        await bot.send_message(user_id, reminder_text)
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {user_id}: {e}")


async def schedule_booking_reminder(booking_datetime, bot, user_id, master_name):
    reminder_time = booking_datetime - timedelta(days=1)
    reminder_time = reminder_time.replace(hour=8, minute=0, second=0, microsecond=0)

    if reminder_time < datetime.now():
        logger.info(
            f"Время напоминания уже прошло ({reminder_time}). "
            f"Отправляем напоминание сразу пользователю {user_id}."
        )
        await send_booking_reminder(bot, user_id, master_name, booking_datetime)
        return

    job = scheduler.add_job(
        send_booking_reminder,
        'date',
        run_date=reminder_time,
        args=[bot, user_id, master_name, booking_datetime]
    )

    logger.info(f"Напоминание запланировано для пользователя {user_id} на {reminder_time}. Job ID: {job.id}")


@router_booking.callback_query(lambda c: c.data.startswith('date_'))
async def process_callback_date(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if await is_flood(user_id, MAX_CLICKS, TIME_WINDOW):
        await callback_query.answer("❌ Подождите немного перед следующим действием! Превышено количество нажатий.",
                                    show_alert=True)
        return
    data = callback_query.data.split('_')
    master_id, date = data[1], data[2]
    logger.debug(f"Пользователь выбрал дату для записи: {date}, мастер ID: {master_id}")
    await callback_query.answer()

    try:
        with SessionFactory() as session:
            schedule = session.query(MasterSchedule).filter(
                MasterSchedule.master_id == master_id
            ).all()
            available_times = []
            for item in schedule:
                available_times.append(f"{item.start_time} - {item.end_time}")

            time_buttons = []
            for time in available_times:
                time_buttons.append(
                    [InlineKeyboardButton(text=f"⏰ {time}", callback_data=f"time_{master_id}_{date}_{time}")])

            markup = InlineKeyboardMarkup(inline_keyboard=time_buttons)
            await callback_query.message.edit_text("🕒 Выберите доступное время для записи:", reply_markup=markup)
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await callback_query.answer("❌ Произошла ошибка при обработке времени.", show_alert=True)

@router_booking.callback_query(lambda c: c.data.startswith('time_'))
async def process_callback_time(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

