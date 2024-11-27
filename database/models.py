import uuid

from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, BigInteger, Integer, Enum, Date, Time, Boolean
from sqlalchemy.orm import relationship
from database.database import Base


## Таблица User
class User(Base):
    __tablename__ = 'user'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    created_at = Column(BigInteger, nullable=False)
    role = Column(String(255), nullable=True)


# Таблица Master
class Master(Base):
    __tablename__ = 'master'

    master_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))  # UUID как строка
    master_name = Column(String(255), nullable=True)
    master_description = Column(String(255), nullable=True)
    master_photo = Column(String(255), nullable=True)


class Booking(Base):
    __tablename__ = 'bookings'

    booking_id = Column(Integer, primary_key=True)
    booking_datetime = Column(DateTime)
    status = Column(String, default="new")
    reminder_job_id = Column(Integer, nullable=True)  # Новая колонка

    user_id = Column(BigInteger, ForeignKey('user.user_id'), nullable=False)
    master_id = Column(String(36), ForeignKey('master.master_id'), nullable=False)

    user = relationship("User", backref="bookings")
    master = relationship("Master", backref="bookings")


# Таблица PriceList
class PriceList(Base):
    __tablename__ = 'price_list'

    price_id = Column(Integer, primary_key=True)
    price_description = Column(String(1024), nullable=True)
    price_photo = Column(String(255), nullable=True)

    def set_description(self, description):
        if not isinstance(description, str):
            raise ValueError("Описание должно быть строкой.")
        self.price_description = description

    def set_photo(self, photo):
        if not isinstance(photo, str):
            raise ValueError("Путь к фото должен быть строкой.")
        self.price_photo = photo


class MasterSchedule(Base):
    __tablename__ = 'master_schedule'

    schedule_id = Column(Integer, primary_key=True)
    master_id = Column(String(36), ForeignKey('master.master_id'), nullable=False)  # ID мастера
    day_of_week = Column(String, nullable=False)  # День недели
    start_time = Column(Time, nullable=False)  # Начало рабочего времени
    end_time = Column(Time, nullable=False)  # Конец рабочего времени
    is_blocked = Column(Boolean, default=False)  # Поле для блокировки

    master = relationship("Master", back_populates="schedules")

Master.schedules = relationship("MasterSchedule", back_populates="master")


class UserSchedule(Base):
    __tablename__ = 'user_schedule'

    schedule_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user.user_id'), nullable=False)  # Связь с пользователем
    day_of_week = Column(String, nullable=False)  # День недели
    date = Column(Date, nullable=False)  # Дата (вместо day_of_week)
    is_blocked = Column(Boolean, default=False)  # Флаг блокировки

    user = relationship("User", backref="user_schedule")
