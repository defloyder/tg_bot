from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.reader import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)

SessionFactory = sessionmaker(bind=engine)

Base = declarative_base()
