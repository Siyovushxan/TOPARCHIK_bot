import asyncio
import os
import logging
import yt_dlp
from config import DOWNLOAD_DIR, YOUTUBE_COOKIES, YOUTUBE_PO_TOKEN, YOUTUBE_VISITOR_DATA

logger = logging.getLogger(__name__)


def get_cookies_path():
    """Cookie faylini tayyorlaydi."""
    if not YOUTUBE_COOKIES:
        logger.warning("YOUTUBE_COOKIES o'rnatilmagan!")
        return None

    raw = YOUTUBE_COOKIES.strip()
    # .env dagi qo'shtirnoqlarni tozalash
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    # Agar fayl yo'li bo'lsa
    if os.path.isfile(raw):
        logger.info(f"Cookie fayldan o'qildi: {raw}")
        return raw

    # Agar Netscape cookie mazmuni bo'lsa
    if "Netscape" in raw or "HTTP Cookie File" in raw or ".youtube.com" in raw:
        cookie_path = os.path.join(DOWNLOAD_DIR, "youtube_cookies.txt")
        # Har doim qaytadan yozish o'rniga, mavjud bo'lsa va hajmi bir xil bo'lsa — qaytadan yozmaymiz
        if os.path.exists(cookie_path) and os.path.getsize(cookie_path) == len(raw):
             return cookie_path
             
        if not raw.startswith("# Netscape"):
            raw = "# Netscape HTTP Cookie File\n" + raw
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(raw)
        logger.info(f"Cookie yozildi: {cookie_path} ({len(raw)} bayt)")
        return cookie_path

    logger.warning("YOUTUBE_COOKIES noto'g'ri format!")
    return None


def build_youtube_profile() -> dict:
    """yt-dlp uchun YouTube extractor argumentlari."""
    youtube_args: dict = {
        # Mobil mijozlar kamroq bloklanadi, shuning uchun ularni birinchi qo'yamiz
        "player_client": ["android", "ios", "mweb"],
        "force_ipv4": True,
    }
    if YOUTUBE_PO_TOKEN:
        youtube_args["po_token"] = [f"web.gvs+{YOUTUBE_PO_TOKEN}"]
    if YOUTUBE_VISITOR_DATA:
        youtube_args["visitor_data"] = [YOUTUBE_VISITOR_DATA]
    return {"extractor_args": {"youtube": youtube_args}}


def get_yt_dlp_opts(outtmpl: str, audio_only: bool = True) -> dict:
    """yt-dlp uchun parametrlar."""
    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "extractor_retries": 5,
        "retries": 10,
        "cookiefile": get_cookies_path(),
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
        "ignoreerrors": False,
        "no_color": True,
        "source_address": "0.0.0.0", # IPv4 ni majburlash
    }

    if audio_only:
        opts.update({
            # Formatni eng sodda holatga keltiramiz
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
        "cookiefile": cookie_path,
        "no_warnings": True,
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
    }

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
                
                # Check for post-processed mp3
                if audio_only:
                    base_path = os.path.splitext(final_filename)[0]
                    mp3_path = base_path + ".mp3"
                    if os.path.exists(mp3_path):
                        return _info, mp3_path
                
                return _info, final_filename
        except Exception as e:
            msg = str(e)
            if "format is not available" in msg:
                msg = "Ushbu audioga ruxsat berilmadi yoki format topilmadi. Iltimos boshqa variantni tanlang."
            logger.error(f"Download error for {url}: {e}")
            raise Exception(msg)

    loop = asyncio.get_event_loop()
    try:
        info, final_path = await loop.run_in_executor(None, _download)
    except Exception as e:
        logger.error(f"Executor error: {e}")
        raise e

    # Backup check for file existence
    if not os.path.exists(final_path):
        base_path = os.path.splitext(final_path)[0]
        for ext in ['.mp3', '.m4a', '.webm', '.mp4']:
            if os.path.exists(base_path + ext):
                final_path = base_path + ext
                break
    
    if not os.path.exists(final_path):
         raise Exception("Fayl yuklandi, lekin saqlashda xato yuz berdi (topilmadi).")

    return info, final_path
