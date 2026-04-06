import asyncio
import signal
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from toparchik_bot import config
from toparchik_bot.handlers import common, media, docs, admin, webapp as webapp_handlers

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

def setup_routers(dp: Dispatcher):
    dp.include_router(admin.router)
    dp.include_router(common.router)
    dp.include_router(docs.router)
    dp.include_router(media.router)

async def on_startup(bot: Bot):
    # Webhook setting (if Railway is used)
    if config.RAILWAY_PUBLIC_DOMAIN:
        webhook_url = f"https://{config.RAILWAY_PUBLIC_DOMAIN}{config.WEBHOOK_PATH}"
        logger.info(f"Setting webhook to: {webhook_url}")
        await bot.set_webhook(url=webhook_url, secret_token=config.WEBHOOK_SECRET)
    else:
        await bot.delete_webhook(drop_pending_updates=True)

    # Sync archive if configured
    if config.ARCHIVE_SYNC_ON_START:
        logger.info("ARCHIVE_SYNC_ON_START is enabled. Starting sync...")
        asyncio.create_task(admin.sync_archive_from_channel(bot, None))

async def main():
    setup_routers(dp)
    dp.startup.register(on_startup)

    # Web App initialization
    app = web.Application()
    
    # API endpoints
    app.router.add_get("/api/top", webapp_handlers.handle_api_top)
    app.router.add_get("/api/platform/{platform}", webapp_handlers.handle_api_platform)
    app.router.add_get("/api/artists", webapp_handlers.handle_api_artists)
    app.router.add_get("/api/artist/{artist}", webapp_handlers.handle_api_artist)
    app.router.add_get("/api/search", webapp_handlers.handle_api_search)

    # Webhook or Polling
    if config.RAILWAY_PUBLIC_DOMAIN:
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
            secret_token=config.WEBHOOK_SECRET,
        )
        webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
        await site.start()
        logger.info(f"Bot started via Webhook on port {os.getenv('PORT', 8080)}")
        await asyncio.Event().wait()
    else:
        # Simple Polling with health check server
        async def start_polling():
            logger.info("Bot v2.1 (Enhanced Premium) starting in polling mode...")
            await dp.start_polling(bot)

        app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
        await site.start()
        logger.info(f"Health check server started on port {os.getenv('PORT', 8080)}")
        
        await start_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
