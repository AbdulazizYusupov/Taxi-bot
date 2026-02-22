import asyncio
import logging
import os
from dotenv import load_dotenv

# Render uchun kerakli kutubxona
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeDefault, MenuButtonCommands

from database.db import init_db
from handlers import common, client, driver
from keyboards.keyboards import MENU_COMMANDS

# .env faylini yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- RENDER UCHUN WEB SERVER QISMI (PORT OCHISH UCHUN) ---
async def handle(request):
    """Render uchun 'men tirikman' deb javob beruvchi funksiya"""
    return web.Response(text="Bot is running!")

async def start_webhook_server():
    """Render portini ochib beruvchi server"""
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render avtomatik PORT beradi, bo'lmasa 8080 ishlatiladi
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"✅ Web server started on port {port}")
# -------------------------------------------------------

async def main():
    # Bot obyektini yaratish
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Dispatcher va xotira sozlamasi
    dp = Dispatcher(storage=MemoryStorage())

    # Routerlarni ro'yxatdan o'tkazish
    dp.include_router(common.router)
    dp.include_router(driver.router)
    dp.include_router(client.router)

    # 1. Ma'lumotlar bazasini ishga tushirish
    await init_db()
    logger.info("✅ Database initialized")

    # 2. Menyu komandalarini o'rnatish
    await bot.set_my_commands(MENU_COMMANDS, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("✅ Menu commands set")

    logger.info("🚀 Bot va Web Server ishga tushmoqda...")

    # 3. Web server va Pollingni PARALLEL (bir vaqtda) ishga tushirish
    # Bu Render port scan timeout xatosini oldini oladi
    await asyncio.gather(
        start_webhook_server(),
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.error("Bot stopped!")