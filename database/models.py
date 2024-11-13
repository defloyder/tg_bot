from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import relationship

from database.database import Base


# Таблица User
class User(Base):
    __tablename__ = 'user'

    user_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    created_at = Column(BigInteger, nullable=False)
    role = Column(String(255), nullable=True)

    # Таблица Record
class Booking(Base):
    __tablename__ = 'booking'

    booking_id = Column(Integer, primary_key=True)
    booking_datetime = Column(DateTime, nullable=True)


# Таблица Master
class Master(Base):
    __tablename__ = 'master'

    master_id = Column(Integer, primary_key=True)
    master_name = Column(String(255), nullable=True)
    master_description = Column(String(255), nullable=True)
    master_photo = Column(String(255), nullable=True)

