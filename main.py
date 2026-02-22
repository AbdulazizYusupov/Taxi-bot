import asyncio
import logging
import os
from dotenv import load_dotenv

# Render uchun kerakli kutubxonalar
from aiohttp import web
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

# --- RENDER UCHUN WEB SERVER QISMI ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_webhook_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render avtomatik PORT beradi, bo'lmasa 8080 ishlatiladi
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Web server started on port {port}")
# -------------------------------------

async def main():
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(driver.router)
    dp.include_router(client.router)

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Renderda portni ochib qo'yish
    await start_webhook_server()

    # Set left menu button commands
    await bot.set_my_commands(MENU_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("✅ Menu commands set")

    logger.info("🚀 Bot starting...")
    
    # Telegramdan xabarlarni kutish
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Bot stopped!")