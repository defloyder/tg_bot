from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_engine('sqlite:///database.db')

session = sessionmaker(bind=engine)

# Создаем базу для декларативного метода
Base = declarative_base()


def create_tables():
    Base.metadata.create_all(engine)

