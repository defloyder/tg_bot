import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger, Integer, Date, Time, \
    Boolean
from sqlalchemy.orm import relationship

from database.database import Base


class User(Base):
    __tablename__ = 'user'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    created_at = Column(BigInteger, nullable=False)
    role = Column(String(255), nullable=True)


class Master(Base):
    __tablename__ = 'master'

    master_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
    master_id = Column(String(36), ForeignKey('master.master_id'), nullable=False)
    day_of_week = Column(String, nullable=False)
    date = Column(Date, nullable=True)  # Поле для конкретной даты
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_blocked = Column(Boolean, default=False)

    master = relationship("Master", back_populates="schedules")


Master.schedules = relationship("MasterSchedule", back_populates="master")


class UserSchedule(Base):
    __tablename__ = 'user_schedule'

    schedule_id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('user.user_id'), nullable=False)
    day_of_week = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    is_blocked = Column(Boolean, default=False)

    user = relationship("User", backref="user_schedule")
