import asyncio
import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, YOUTUBE_COOKIES, YOUTUBE_PO_TOKEN, YOUTUBE_VISITOR_DATA

logger = logging.getLogger(__name__)


def get_cookies_path():
    """
    Cookie faylini tayyorlaydi.
    YOUTUBE_COOKIES o'zgaruvchisi fayl yo'li yoki Netscape formati mazmuni bo'lishi mumkin.
    """
    if not YOUTUBE_COOKIES:
        logger.warning("YOUTUBE_COOKIES o'rnatilmagan. Bot detection xatosi bo'lishi mumkin!")
        return None

    # .env faylida qo'yilgan qo'shtirnoqlarni tozalash
    raw = YOUTUBE_COOKIES.strip()
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    # Agar to'g'ridan-to'g'ri fayl yo'li bo'lsa
    if os.path.isfile(raw):
        logger.info(f"YouTube cookies fayldan o'qildi: {raw}")
        return raw

    # Agar Netscape cookie mazmuni bo'lsa — faylga yozamiz
    if "Netscape" in raw or "HTTP Cookie File" in raw or ".youtube.com" in raw:
        cookie_path = os.path.join(DOWNLOAD_DIR, "youtube_cookies.txt")
        # Agar Netscape sarlavhasi yo'q bo'lsa, uni qo'shib qo'yamiz
        if not raw.startswith("# Netscape"):
            raw = "# Netscape HTTP Cookie File\n" + raw
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(raw)
        logger.info(f"YouTube cookies yozildi: {cookie_path} ({len(raw)} bayt)")
        return cookie_path

    logger.warning("YOUTUBE_COOKIES to'g'ri formatda emas. Cookie ishlatilmaydi.")
    return None


def build_youtube_profile() -> dict:
    """
    yt-dlp extractor argumentlarini tuzadi.
    iOS va mweb klientlari server IP'larida kamroq bloklash beradi.
    """
    clients = ["ios", "mweb", "android", "web"]

    youtube_args: dict = {
        "player_client": clients,
    }

    if YOUTUBE_PO_TOKEN:
        youtube_args["po_token"] = [f"mweb.gvs+{YOUTUBE_PO_TOKEN}", f"web+{YOUTUBE_PO_TOKEN}"]

    if YOUTUBE_VISITOR_DATA:
        youtube_args["visitor_data"] = [YOUTUBE_VISITOR_DATA]

    return {"extractor_args": {"youtube": youtube_args}}


def get_yt_dlp_opts(outtmpl: str, audio_only: bool = True) -> dict:
    cookie_file = get_cookies_path()
    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "noprogress": True,
        "extractor_retries": 5,
        "retries": 3,
        "cookiefile": cookie_file,
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
    }

    if audio_only:
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts.update({
            "format": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        })

    return opts


async def search_youtube(query: str, max_results: int = 10):
    """YouTube dan asinxron qidirish."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "noplaylist": True,
        "cookiefile": get_cookies_path(),
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
    }

    def _search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return info.get("entries", []) if info else []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)


async def download_media(url: str, chat_id: int, audio_only: bool = True):
    """Media (YouTube, TikTok, Instagram) yuklab olish."""
    file_id = f"{chat_id}_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(DOWNLOAD_DIR, file_id)
    outtmpl = f"{file_path}.%(ext)s"

    opts = get_yt_dlp_opts(outtmpl, audio_only)

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            _info = ydl.extract_info(url, download=True)
            return _info, ydl.prepare_filename(_info)

    loop = asyncio.get_event_loop()
    info, final_path = await loop.run_in_executor(None, _download)

    if audio_only and not final_path.endswith(".mp3"):
        final_path = os.path.splitext(final_path)[0] + ".mp3"

    return info, final_path
