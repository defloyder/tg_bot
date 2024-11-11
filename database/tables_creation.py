# database/tables_creation.py

from logger_config import logger  # Импортируем настроенный логгер
from database.database import Base, engine

def create_tables():
    logger.debug("Создание таблиц...")
    try:
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        logger.success("Таблицы успешно созданы.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
