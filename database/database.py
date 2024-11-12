from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.reader import settings
from logger_config import logger


logger.debug("Setting up database connection URL...")
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
)
logger.success("Database connection URL set successfully.")


SessionFactory = sessionmaker(bind=engine)
Base = declarative_base()

def check_database_connection():
    logger.debug("Attempting to connect to the database...")
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.success("Database connected successfully!")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise e
