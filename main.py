import asyncio
import logging

from Src.Handlers import get_handlers_router
from Src.Handlers.Booking.booking_handler import scheduler
from database.tables_creation import create_tables
from loader import bot, dp
from logger_config import logger

logging.basicConfig(level=logging.INFO)
async def on_shutdown():
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.session.close()
    logger.debug("Bot session stopped")

async def on_startup():
    create_tables()
    dp.include_router(get_handlers_router())
    logger.debug("Bot session started")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запуск процесса поллинга новых апдейтов
    await dp.start_polling(bot)

if __name__ == '__main__':
    scheduler.start()
    asyncio.run(main())  # Это важно!
