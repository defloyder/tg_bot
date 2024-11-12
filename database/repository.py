import time

from aiogram import types
from sqlalchemy.dialects.sqlite import insert

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
    user = session.query(User).filter(User.user_id == user_id).first()
    if user:
        session.delete(user)
        session.commit()
    return user


from database.database import SessionFactory
from logger_config import logger


def create_record(session, datetime_value):
    try:
        # Создание новой записи без использования user_id и master_id
        new_record = Booking(record_datetime=datetime_value)

        # Добавление записи в сессию
        session.add(new_record)

        # Фиксация изменений в базе
        session.commit()

        # Логирование успешной записи
        logger.info(f"Запись создана: {new_record}")
        return new_record
    except Exception as e:
        # Логирование ошибок
        logger.error(f"Ошибка при создании записи: {e}")
        session.rollback()  # Откатываем изменения в случае ошибки
        return None


def get_record_by_id(session, record_id):
    try:
        record = session.query(Booking).filter(Booking.record_id == record_id).first()
        return record
    except Exception as e:
        logger.error(f"Error fetching record by ID: {e}")
        return None

def get_all_records(session):
    try:
        records = session.query(Booking).all()
        return records
    except Exception as e:
        logger.error(f"Error fetching all records: {e}")
        return []

def update_record_datetime(session, record_id, new_datetime):
    try:
        record = session.query(Booking).filter(Booking.record_id == record_id).first()
        if record:
            record.record_datetime = new_datetime
            session.commit()
            logger.debug(f"Record updated successfully: ID {record_id}")
            return record
        logger.warning(f"Record not found: ID {record_id}")
        return None
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating record: {e}")
        return None

def delete_record(session, record_id):
    try:
        record = session.query(Booking).filter(Booking.record_id == record_id).first()
        if record:
            session.delete(record)
            session.commit()
            logger.debug(f"Record deleted successfully: ID {record_id}")
            return True
        logger.warning(f"Record not found for deletion: ID {record_id}")
        return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting record: {e}")
        return False

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
