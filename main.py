import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeDefault, MenuButtonCommands

from database.db import init_db
from handlers import common, client, driver
from keyboards.keyboards import MENU_COMMANDS

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers (ORDER MATTERS!)
    dp.include_router(common.router)
    dp.include_router(driver.router)
    dp.include_router(client.router)

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Set left menu button commands
    await bot.set_my_commands(MENU_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("✅ Menu commands set")

    logger.info("🚀 Bot starting...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
