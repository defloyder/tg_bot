import time

from aiogram import types
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from datetime import datetime

from database import User
from database import Booking

from logger_config import logger


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
        logger.error(e)


def get_user_by_id(session, user_id):
    return session.query(User).filter(User.user_id == user_id).first()


def update_user_username(session, user_id, new_nickname):
    user = session.query(User).filter(User.user_id == user_id).first()
    if user:
        user.nickname = new_nickname
        session.commit()
    return user


def delete_user(session, user_id):
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        session.delete(user)
        session.commit()
    return user

#
# def create_master(session, name, description=None, photo=None):
#     new_master = Master(name=name, description=description, photo=photo)
#     session.add(new_master)
#     session.commit()
#     return new_master
#
#
# def get_master_by_id(session, master_id):
#     return session.query(Master).filter(Master.id == master_id).first()
#
#
# def update_master(session, master_id, name=None, description=None, photo=None):
#     master = session.query(Master).filter(Master.id == master_id).first()
#     if master:
#         if name:
#             master.name = name
#         if description:
#             master.description = description
#         if photo:
#             master.photo = photo
#         session.commit()
#     return master
#
#
# def delete_master(session, master_id):
#     master = session.query(Master).filter(Master.id == master_id).first()
#     if master:
#         session.delete(master)
#         session.commit()
#     return master
#
#
def create_record(session: Session, datetime_value: str):
    try:
        # Преобразуем строку в datetime объект
        booking_datetime = datetime.strptime(datetime_value, '%d.%m.%Y %H:%M')

        # Создаем новый объект Booking
        new_record = Booking(
            booking_datetime=booking_datetime  # убедитесь, что используете правильное поле
        )

        # Добавляем в сессию и сохраняем
        session.add(new_record)
        session.commit()
        logger.info(f"Запись успешно добавлена в базу данных: {new_record}")
        return new_record

    except Exception as e:
        session.rollback()  # откатываем транзакцию в случае ошибки
        logger.error(f"Ошибка при создании записи: {e}")
        return None


def get_record_by_id(session: Session, record_id: int):
    try:
        return session.query(Booking).filter(Booking.id == record_id).first()
    except Exception as e:
        logger.error(f"Ошибка при получении записи с ID {record_id}: {e}")
        return None


def update_record_datetime(session: Session, record_id: int, new_datetime: str):
    try:
        # Преобразуем строку в datetime объект
        updated_datetime = datetime.strptime(new_datetime, '%d.%m.%Y %H:%M')

        # Ищем запись
        record = session.query(Booking).filter(Booking.id == record_id).first()

        if record:
            # Обновляем дату и время записи
            record.booking_datetime = updated_datetime
            session.commit()  # Сохраняем изменения
            return record
        else:
            return None
    except Exception as e:
        session.rollback()  # откатываем транзакцию в случае ошибки
        logger.error(f"Ошибка при обновлении записи с ID {record_id}: {e}")
        return None


def delete_record(session: Session, record_id: int):
    try:
        # Ищем запись
        record = session.query(Booking).filter(Booking.id == record_id).first()

        if record:
            session.delete(record)
            session.commit()  # Сохраняем изменения
            return record
        else:
            return None
    except Exception as e:
        session.rollback()  # откатываем транзакцию в случае ошибки
        logger.error(f"Ошибка при удалении записи с ID {record_id}: {e}")
        return None
