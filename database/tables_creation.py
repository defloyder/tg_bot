from asyncio.log import logger

from database.database import Base, engine

def create_tables():
    logger.info("Создание таблиц...")
    try:
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn)
        logger.info("Таблицы успешно созданы.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
