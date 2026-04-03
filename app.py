import asyncio
<<<<<<< HEAD
import logging
import os
import re
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, FSInputFile, Message
from urllib.parse import quote_plus, unquote_plus
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

import config
from services.gemini import ask_gemini
from services.youtube import search_youtube, download_media
from services.archive import archive_service
from services.docs import convert_pdf_to_docx, run_conversion

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot initialization
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# --- Keyboards ---

# Agar Railway yoki boshqa muhit root app.py ni ishga tushirsa,
# faqat toparchik_bot.app modulini chaqiramiz (asosiy logika faqat bitta joyda bo'ladi)
try:
    from toparchik_bot.app import main
except Exception as e:
    raise RuntimeError("toparchik_bot.app modulini yuklab bo‘lmadi: %s" % e)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
def main_menu():
