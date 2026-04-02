import asyncio
import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, YOUTUBE_COOKIES, YOUTUBE_PO_TOKEN, YOUTUBE_VISITOR_DATA

logger = logging.getLogger(__name__)


def get_cookies_path():
    """Cookie faylini tayyorlaydi."""
    if not YOUTUBE_COOKIES:
        logger.warning("YOUTUBE_COOKIES o'rnatilmagan — cookie siz urinib ko'riladi.")
        return None

    raw = YOUTUBE_COOKIES.strip()
    # .env dagi qo'shtirnoqlarni tozalash
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    # Agar fayl yo'li bo'lsa
    if os.path.isfile(raw):
        size = os.path.getsize(raw)
        if size < 500:
            logger.error(f"Cookie fayl juda kichik ({size} bayt) — yaroqsiz!")
            return None
        logger.info(f"Cookie fayldan o'qildi: {raw} ({size} bayt)")
        return raw

    # Agar Netscape cookie mazmuni bo'lsa
    if "Netscape" in raw or "HTTP Cookie File" in raw or ".youtube.com" in raw:
        cookie_path = os.path.join(DOWNLOAD_DIR, "youtube_cookies.txt")

        # Header qo'shish (agar yo'q bo'lsa)
        if not raw.startswith("# Netscape"):
            raw = "# Netscape HTTP Cookie File\n" + raw

        # Mavjud bo'lsa va mazmuni bir xil bo'lsa — qaytadan yozmaymiz
        if os.path.exists(cookie_path):
            with open(cookie_path, "r", encoding="utf-8") as f:
                if f.read() == raw:
                    size = os.path.getsize(cookie_path)
                    if size < 500:
                        logger.error(f"Mavjud cookie fayl juda kichik ({size} bayt) — yaroqsiz!")
                        return None
                    return cookie_path

        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(raw)

        size = os.path.getsize(cookie_path)
        if size < 500:
            logger.error(f"Yozilgan cookie fayl juda kichik ({size} bayt) — yaroqsiz!")
            return None

        logger.info(f"Cookie yozildi: {cookie_path} ({size} bayt)")
        return cookie_path

    logger.warning("YOUTUBE_COOKIES noto'g'ri format — cookie siz urinib ko'riladi.")
    return None


def build_youtube_profile() -> dict:
    """yt-dlp uchun YouTube extractor argumentlari.
    
    ios va android clientlari cookie talab qilmaydi va
    YouTube tomonidan kamroq bloklanadi.
    """
    youtube_args: dict = {
        "player_client": ["ios", "android"],
        "force_ipv4": True,
    }
    if YOUTUBE_PO_TOKEN:
        youtube_args["po_token"] = [f"web.gvs+{YOUTUBE_PO_TOKEN}"]
    if YOUTUBE_VISITOR_DATA:
        youtube_args["visitor_data"] = [YOUTUBE_VISITOR_DATA]
    return {"extractor_args": {"youtube": youtube_args}}


def get_yt_dlp_opts(outtmpl: str, audio_only: bool = True) -> dict:
    """yt-dlp uchun parametrlar."""
    cookie_path = get_cookies_path()

    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "extractor_retries": 10,
        "retries": 10,
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
        "ignoreerrors": False,
        "no_color": True,
        "source_address": "0.0.0.0",
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
        "concurrent_fragment_downloads": 4,
        "geo_bypass": True,
        "nocheckcertificate": True,
    }

    # Cookie faqat mavjud va yaroqli bo'lganda qo'shiladi
    if cookie_path:
        opts["cookiefile"] = cookie_path

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
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
        })

    return opts


async def search_youtube(query: str, max_results: int = 10):
    """YouTube dan asinxron qidirish."""
    cookie_path = get_cookies_path()

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "noplaylist": True,
        "no_warnings": True,
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    def _search():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                return info.get("entries", []) if info else []
        except Exception as e:
            logger.error(f"yt-dlp search error: {e}")
            return []

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)


async def download_media(url: str, chat_id: int, audio_only: bool = True):
    """Media (YouTube, TikTok, Instagram) yuklab olish."""
    file_id = f"{chat_id}_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(DOWNLOAD_DIR, file_id)
    outtmpl = f"{file_path}.%(ext)s"

    opts = get_yt_dlp_opts(outtmpl, audio_only)

    def _download():
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                _info = ydl.extract_info(url, download=True)
                final_filename = ydl.prepare_filename(_info)

                if audio_only:
                    base_path = os.path.splitext(final_filename)[0]
                    mp3_path = base_path + ".mp3"
                    if os.path.exists(mp3_path):
                        return _info, mp3_path

                return _info, final_filename
        except Exception as e:
            msg = str(e)
            if "Sign in to confirm" in msg or "bot" in msg.lower():
                msg = (
                    "YouTube bot tekshiruvi: cookie muammosi yoki IP bloklangan. "
                    "Iltimos cookie ni yangilang yoki keyinroq urinib ko'ring."
                )
            elif "format is not available" in msg:
                msg = "Ushbu audioga ruxsat berilmadi yoki format topilmadi."
            logger.error(f"Download error for {url}: {e}")
            raise Exception(msg)

    loop = asyncio.get_event_loop()
    info, final_path = await loop.run_in_executor(None, _download)

    # Backup: boshqa kengaytmalarni tekshirish
    if not os.path.exists(final_path):
        base_path = os.path.splitext(final_path)[0]
        for ext in ['.mp3', '.m4a', '.webm', '.mp4', '.opus']:
            candidate = base_path + ext
            if os.path.exists(candidate):
                final_path = candidate
                break

    if not os.path.exists(final_path):
        raise Exception("Fayl yuklandi, lekin saqlashda xato yuz berdi (topilmadi).")

    return info, final_path