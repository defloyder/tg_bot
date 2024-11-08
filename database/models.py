from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from database.database import Base


# Таблица User
class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    nickname = Column(String(255), nullable=True)

    # Связь с таблицей "Записи"
    records = relationship("Record", back_populates="user")

# Таблица Master
class Master(Base):
    __tablename__ = 'master'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    photo = Column(String(255), nullable=True)

    # Связь с таблицей "Записи"
    records = relationship("Record", back_populates="master")

# Таблица Record
class Record(Base):
    __tablename__ = 'record'

    id = Column(Integer, primary_key=True)
    datetime = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    master_id = Column(Integer, ForeignKey('master.id'))

    # Связь с таблицами "User" и "Master"
    user = relationship("User", back_populates="records")
    master = relationship("Master", back_populates="records")
