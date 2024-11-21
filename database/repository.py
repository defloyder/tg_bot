import time
import uuid

from aiogram import types
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from datetime import datetime
from database import User, Booking, Master
from logger_config import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

# Создание пользователя
def create_user(session, event: types.Message):
    user_id = event.from_user.id
    username = event.from_user.username
    role = "user"
    created_at = round(time.time())

    user_data = {"user_id": user_id,
                 "username": username,
                 "role": role,
                 "created_at": created_at}

    try:
        statement = insert(User).values(**user_data)
        statement = statement.on_conflict_do_nothing(index_elements=['user_id'])
        session.execute(statement)
        session.commit()
        logger.debug(f"User created successfully {user_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating user {user_id}: {e}")

# Получение пользователя по ID
def get_user_by_id(session, user_id):
    return session.query(User).filter(User.user_id == user_id).first()

# Обновление имени пользователя
def update_user_username(session, user_id, new_nickname):
    user = session.query(User).filter(User.user_id == user_id).first()
    if user:
        user.nickname = new_nickname
        session.commit()
    return user



# Создание мастера
def create_master(session, master_name, master_description=None, master_photo=None):
    new_master = Master(
        master_id=str(uuid.uuid4()),  # Генерация уникального идентификатора
        master_name=master_name,
        master_description=master_description,
        master_photo=master_photo
    )
    session.add(new_master)
    session.commit()
    return new_master

def get_master_by_id(session, master_id: str):
    return session.query(Master).filter(Master.master_id == master_id).first()


# Удаление мастера
def delete_master(session, master_id: str):
    master = session.query(Master).filter(Master.master_id == master_id).first()
    if master:
        session.delete(master)
        session.commit()
        return True
    return False


# Обновление данных мастера
def update_master(session, master_id, master_name=None, master_description=None, master_photo=None):
    master = session.query(Master).filter(Master.master_id == master_id).first()
    if master:
        if master_name:
            master.master_name = master_name
        if master_description:
            master.master_description = master_description
        if master_photo:
            master.master_photo = master_photo
        session.commit()
    return master

# Создание записи
def create_booking(session, booking_datetime, master_id: str, user_id: int, status="new"):
    try:
        new_booking = Booking(
            booking_datetime=booking_datetime,
            status=status,
            master_id=master_id,
            user_id=user_id
        )
        session.add(new_booking)
        session.commit()
        return new_booking
    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        session.rollback()  # Откатываем изменения в случае ошибки
        return None


# Получение записи по ID
def get_record_by_id(session: Session, record_id: int):
    try:
        return session.query(Booking).filter(Booking.id == record_id).first()
    except Exception as e:
        logger.error(f"Ошибка при получении записи с ID {record_id}: {e}")
        return None

# Получение занятых дат для мастера
def get_booked_dates_for_master(session, master_id: str):
    try:
        booked_dates = session.query(Booking.booking_datetime).filter(Booking.master_id == master_id).all()
        return {booking.booking_datetime.date() for booking in booked_dates}  # Возвращаем только даты
    except Exception as e:
        logger.error(f"Ошибка при запросе занятых дат для мастера {master_id}: {e}")
        return set()

def update_record_datetime(session: Session, record_id: int, new_datetime: str):
    try:
        updated_datetime = datetime.strptime(new_datetime, '%d.%m.%Y %H:%M')
        record = session.query(Booking).filter(Booking.id == record_id).first()
        if record:
            record.booking_datetime = updated_datetime
            session.commit()
            return record
        else:
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при обновлении записи с ID {record_id}: {e}")
        return None

def delete_record(session: Session, record_id: int):
    try:
        record = session.query(Booking).filter(Booking.id == record_id).first()
        if record:
            session.delete(record)
            session.commit()
            return record
        else:
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка при удалении записи с ID {record_id}: {e}")
        return None


