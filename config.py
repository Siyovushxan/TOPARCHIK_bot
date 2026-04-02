import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(Path(BASE_DIR) / ".env")

# Telegram Bot API
BOT_TOKEN = os.getenv("BOT_TOKEN")

# AI Services
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")  # Required for Whisper API

# Archive & Cache
ARCHIVE_CHANNEL = os.getenv("ARCHIVE_CHANNEL", "@toparchik_ai")
# If the channel is private, use the numeric ID starting with -100
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")

# YouTube / Media
YOUTUBE_COOKIES = os.getenv("YOUTUBE_COOKIES")
YOUTUBE_COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_PATH")
YOUTUBE_PO_TOKEN = os.getenv("YOUTUBE_PO_TOKEN")
YOUTUBE_VISITOR_DATA = os.getenv("YOUTUBE_VISITOR_DATA")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Web App
WEB_APP_URL = os.getenv("WEB_APP_URL", "")

# Directories
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
CACHE_FILE = os.path.join(BASE_DIR, "cache_index.json")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
