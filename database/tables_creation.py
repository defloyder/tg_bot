# database/tables_creation.py

from logger_config import logger  # Импортируем настроенный логгер
from database.database import Base, engine

def create_tables():
    logger.debug("Creation...")
    try:
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        logger.success("Tables created successfully.")
    except Exception as e:
        logger.error(f"Table error {e}")
