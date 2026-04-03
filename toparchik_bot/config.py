import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# Load .env from the package directory if present, otherwise fall back to the repository root.
load_dotenv(Path(BASE_DIR) / ".env")
load_dotenv(Path(ROOT_DIR) / ".env")

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
YOUTUBE_COOKIES_B64 = os.getenv("YOUTUBE_COOKIES_B64")
YOUTUBE_COOKIES_PATH = os.getenv("YOUTUBE_COOKIES_PATH")
YOUTUBE_PO_TOKEN = os.getenv("YOUTUBE_PO_TOKEN")
YOUTUBE_VISITOR_DATA = os.getenv("YOUTUBE_VISITOR_DATA")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Web App
WEB_APP_URL = os.getenv("WEB_APP_URL", "")

# Admin / Sync
def _parse_int_env(name: str):
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except Exception:
        return None

ADMIN_IDS = {
    int(item.strip())
    for item in (os.getenv("ADMIN_IDS", "") or "").split(",")
    if item.strip().isdigit()
}
SYNC_CHAT_ID = _parse_int_env("SYNC_CHAT_ID")
ARCHIVE_SYNC_MAX = int(os.getenv("ARCHIVE_SYNC_MAX", "2000"))
ARCHIVE_SYNC_GAP = int(os.getenv("ARCHIVE_SYNC_GAP", "200"))
ARCHIVE_SYNC_DELAY = float(os.getenv("ARCHIVE_SYNC_DELAY", "0.25"))
ARCHIVE_SYNC_ON_START = os.getenv("ARCHIVE_SYNC_ON_START", "0") == "1"

# Directories
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
CACHE_FILE = os.path.join(BASE_DIR, "cache_index.json")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
