import time
from datetime import datetime
from aiogram import types
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from database import User, Booking, Master
from logger_config import logger


def create_user(session: Session, event: types.Message):
    """
    Creates a new user in the database if they do not already exist.
    """
    user_id = event.from_user.id
    username = event.from_user.username
    role = "user"
    created_at = round(time.time())

    user_data = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "created_at": created_at
    }

    try:
        statement = insert(User).values(**user_data).on_conflict_do_nothing(index_elements=['user_id'])
        session.execute(statement)
        session.commit()
        logger.debug(f"User created successfully: {user_id}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating user {user_id}: {e}")


def get_user_by_id(session: Session, user_id: int):
    """
    Retrieves a user by their ID.
    """
    try:
        return session.query(User).filter(User.user_id == user_id).first()
    except Exception as e:
        logger.error(f"Error fetching user with ID {user_id}: {e}")
        return None


def update_user_username(session: Session, user_id: int, new_username: str):
    """
    Updates the username of a user.
    """
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.username = new_username
            session.commit()
            logger.info(f"User {user_id} username updated to {new_username}")
            return user
        else:
            logger.warning(f"User with ID {user_id} not found.")
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating username for user {user_id}: {e}")
        return None


def create_master(session: Session, master_name: str, master_description: str = None, master_photo: str = None):
    """
    Creates a new master record.
    """
    try:
        new_master = Master(master_name=master_name, master_description=master_description, master_photo=master_photo)
        session.add(new_master)
        session.commit()
        logger.info(f"Master created successfully: {new_master}")
        return new_master
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating master: {e}")
        return None


def get_master_by_id(session: Session, master_id: int):
    """
    Retrieves a master by their ID.
    """
    try:
        return session.query(Master).filter(Master.master_id == master_id).first()
    except Exception as e:
        logger.error(f"Error fetching master with ID {master_id}: {e}")
        return None


def update_master(session: Session, master_id: int, master_name: str = None, master_description: str = None, master_photo: str = None):
    """
    Updates master details.
    """
    try:
        master = session.query(Master).filter(Master.master_id == master_id).first()
        if master:
            if master_name:
                master.master_name = master_name
            if master_description:
                master.master_description = master_description
            if master_photo:
                master.master_photo = master_photo
            session.commit()
            logger.info(f"Master {master_id} updated successfully.")
            return master
        else:
            logger.warning(f"Master with ID {master_id} not found.")
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating master {master_id}: {e}")
        return None


def delete_master(session: Session, master_id: int):
    """
    Deletes a master record.
    """
    try:
        master = session.query(Master).filter(Master.master_id == master_id).first()
        if master:
            session.delete(master)
            session.commit()
            logger.info(f"Master {master_id} deleted successfully.")
            return True
        else:
            logger.warning(f"Master with ID {master_id} not found.")
            return False
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting master {master_id}: {e}")
        return False


def create_record(session: Session, datetime_value: str):
    """
    Creates a new booking record.
    """
    try:
        booking_datetime = datetime.strptime(datetime_value, '%d.%m.%Y %H:%M')
        new_record = Booking(booking_datetime=booking_datetime)
        session.add(new_record)
        session.commit()
        logger.info(f"Booking record created successfully: {new_record}")
        return new_record
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating booking record: {e}")
        return None


def get_record_by_id(session: Session, record_id: int):
    """
    Retrieves a booking record by ID.
    """
    try:
        return session.query(Booking).filter(Booking.id == record_id).first()
    except Exception as e:
        logger.error(f"Error fetching booking record with ID {record_id}: {e}")
        return None


def update_record_datetime(session: Session, record_id: int, new_datetime: str):
    """
    Updates the datetime of a booking record.
    """
    try:
        updated_datetime = datetime.strptime(new_datetime, '%d.%m.%Y %H:%M')
        record = session.query(Booking).filter(Booking.id == record_id).first()
        if record:
            record.booking_datetime = updated_datetime
            session.commit()
            logger.info(f"Booking record {record_id} updated successfully.")
            return record
        else:
            logger.warning(f"Booking record with ID {record_id} not found.")
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating booking record {record_id}: {e}")
        return None


def delete_record(session: Session, record_id: int):
    """
    Deletes a booking record by ID.
    """
    try:
        record = session.query(Booking).filter(Booking.id == record_id).first()
        if record:
            session.delete(record)
            session.commit()
            logger.info(f"Booking record {record_id} deleted successfully.")
            return record
        else:
            logger.warning(f"Booking record with ID {record_id} not found.")
            return None
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting booking record {record_id}: {e}")
        return None
