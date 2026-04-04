import asyncio
import base64
import os
import re
import logging
import yt_dlp
from googleapiclient.discovery import build
from toparchik_bot.config import (
    DOWNLOAD_DIR,
    DOWNLOAD_CONCURRENCY,
    YOUTUBE_COOKIES,
    YOUTUBE_COOKIES_B64,
    YOUTUBE_COOKIES_PATH,
    YOUTUBE_PO_TOKEN,
    YOUTUBE_VISITOR_DATA,
    YOUTUBE_API_KEY
)

logger = logging.getLogger(__name__)
_cookie_warning_emitted = False
_download_sem = asyncio.Semaphore(max(1, DOWNLOAD_CONCURRENCY))


def _warn_once(message: str):
    global _cookie_warning_emitted
    if not _cookie_warning_emitted:
        logger.warning(message)
        _cookie_warning_emitted = True


def get_cookies_path():
    """Cookie faylini tayyorlaydi."""
    raw = None
    if YOUTUBE_COOKIES_B64:
        raw = YOUTUBE_COOKIES_B64.strip()
    elif YOUTUBE_COOKIES:
        raw = YOUTUBE_COOKIES.strip()
    elif YOUTUBE_COOKIES_PATH:
        raw = YOUTUBE_COOKIES_PATH.strip()

    # If both env vars are missing, try a default local cookie file.
    default_cookie_path = os.path.join(DOWNLOAD_DIR, "youtube_cookies.txt")
    if not raw and os.path.isfile(default_cookie_path):
        logger.info(f"YOUTUBE_COOKIES topilmadi, lekin default cookie fayl topildi: {default_cookie_path}")
        return default_cookie_path

    if not raw:
        _warn_once(
            "YOUTUBE_COOKIES va YOUTUBE_COOKIES_PATH o'rnatilmagan — cookie ishlatilmaydi. "
            "Railway yoki hosting muhitingizga bu qiymatni qo'shing."
        )
        return None

    # .env dagi qo'shtirnoqlarni tozalash
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    if YOUTUBE_COOKIES_B64:
        try:
            decoded = base64.b64decode(raw, validate=True).decode("utf-8")
            raw = decoded.strip()
            logger.info("YOUTUBE_COOKIES_B64 decoded successfully.")
        except Exception as exc:
            logger.error(f"YOUTUBE_COOKIES_B64 decode error: {exc}")
            return None
    else:
        # If base64 accidentally placed into YOUTUBE_COOKIES, try to decode once.
        if ("\n" not in raw and "\t" not in raw and len(raw) > 200 and
                re.fullmatch(r"[A-Za-z0-9+/=]+", raw or "")):
            try:
                decoded = base64.b64decode(raw, validate=True).decode("utf-8")
                if "Netscape" in decoded or ".youtube.com" in decoded:
                    raw = decoded.strip()
                    logger.info("YOUTUBE_COOKIES auto-decoded from base64.")
            except Exception:
                pass

    # Agar fayl yo'li bo'lsa (yoki faqat fayl nomi berilgan bo'lsa)
    candidate_paths = [raw]
    if raw and not os.path.isabs(raw):
        candidate_paths.extend([
            os.path.join(DOWNLOAD_DIR, raw),
            os.path.join(os.getcwd(), raw)
        ])

    for candidate in candidate_paths:
        if os.path.isfile(candidate):
            size = os.path.getsize(candidate)
            if size < 500:
                logger.error(f"Cookie fayl juda kichik ({size} bayt) — yaroqsiz!")
                return None
            logger.info(f"Cookie fayldan o'qildi: {candidate} ({size} bayt)")
            return candidate

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

    if "\n" not in raw and "\t" not in raw:
        _warn_once(
            "YOUTUBE_COOKIES noto'g'ri ko'rinadi: secret ichiga fayl nomi emas, "
            "cookies.txt faylining to'liq matni yoki base64 ko'rinishi kirishi kerak."
        )

    _warn_once("YOUTUBE_COOKIES noto'g'ri format — cookie siz urinib ko'riladi.")
    return None


def build_youtube_profile() -> dict:
    """yt-dlp uchun YouTube extractor argumentlari.
    
    ios va android clientlari serverlarda bloklanish ehtimoli ancha past.
    """
    youtube_args: dict = {
        "player_client": ["web", "android_music", "ios", "android", "mweb", "tv_embedded"],
        "force_ipv4": True,
        "include_dash_manifest": True,
        "include_hls_manifest": True,
    }
    
    # PO Token va Visitor Data ni formatlash
    if YOUTUBE_PO_TOKEN:
        youtube_args["po_token"] = [
            f"web+{YOUTUBE_PO_TOKEN}",
            f"ios+{YOUTUBE_PO_TOKEN}",
            YOUTUBE_PO_TOKEN
        ]
    
    if YOUTUBE_VISITOR_DATA:
        youtube_args["visitor_data"] = [YOUTUBE_VISITOR_DATA]
        
    return {"extractor_args": {"youtube": youtube_args}}


def _parse_iso8601_duration(duration: str) -> int:
    """Convert YouTube ISO 8601 duration to seconds."""
    if not duration:
        return 0

    pattern = re.compile(
        r'^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$'
    )
    match = pattern.match(duration)
    if not match:
        return 0

    days = int(match.group('days') or 0)
    hours = int(match.group('hours') or 0)
    minutes = int(match.group('minutes') or 0)
    seconds = int(match.group('seconds') or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def get_yt_dlp_opts(outtmpl: str, audio_only: bool = True) -> dict:
    """yt-dlp uchun optimallashtirilgan parametrlar."""
    cookie_path = get_cookies_path()
    profile = build_youtube_profile()

    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "extractor_retries": 15,
        "retries": 15,
        "fragment_retries": 15,
        "extractor_args": profile.get("extractor_args", {}),
        "ignoreerrors": False,
        "no_color": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "concurrent_fragment_downloads": 10,  # Tezlikni oshirish uchun
        "socket_timeout": 30,
        "postprocessor_args": {
            "ffmpeg": [
                "-threads", "0",        # Barcha CPU yadrolaridan foydalanish
                "-preset", "veryfast"   # Tezkor konvertatsiya
            ]
        },
        # Browser impersonation (Requires recent yt-dlp)
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "http_headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Cookie faqat mavjud bo'lganda
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


async def compress_audio(input_path: str, target_size_mb: int = 49):
    """Faylni 50 MB dan kichik qilish uchun siqish."""
    import subprocess
    
    current_size = os.path.getsize(input_path) / (1024 * 1024)
    if current_size <= target_size_mb:
        return input_path

    logger.info(f"Fayl hajmi {current_size:.1f} MB. Siqish boshlandi...")
    
    # Videoning davomiyligini aniqlash (ffprobe orqali)
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', input_path
        ]
        duration = float(subprocess.check_output(cmd).decode().strip())
    except Exception as e:
        logger.error(f"Ffprobe error: {e}")
        duration = 300 # 5 min fallback
        
    # Bitrate hisoblash (Hajm = Bitrate * Davomiylik)
    # 49MB * 8192 (bits per MB) / duration
    target_bitrate = int((target_size_mb * 8192) / duration)
    
    # Bitrate juda past bo'lib ketmasligi kerak (minim 32k)
    target_bitrate = max(32, min(target_bitrate, 128))
    
    output_path = input_path.replace(".mp3", "_fixed.mp3")
    
    try:
        # Ffmpeg orqali siqish
        compress_cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-b:a', f'{target_bitrate}k',
            '-map_metadata', '0',
            '-threads', '0',
            output_path
        ]
        subprocess.run(compress_cmd, check=True, capture_output=True)
        
        if os.path.exists(output_path):
            os.remove(input_path)
            return output_path
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        
    return input_path


async def search_youtube(query: str, max_results: int = 10):
    """YouTube dan asinxron qidirish (YouTube Data API v3 orqali)."""
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "Sizning_API_kalitingiz":
        logger.warning("YOUTUBE_API_KEY o'rnatilmagan - yt-dlp ishlatiladi.")
        return await _search_yt_dlp(query, max_results)

    def _search_api():
        try:
            youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
            request = youtube.search().list(
                q=query,
                part="id,snippet",
                type="video",
                maxResults=max_results
            )
            response = request.execute()
            
            results = []
            video_ids = []
            for item in response.get("items", []):
                video_id = item["id"].get("videoId")
                if video_id:
                    results.append({
                        "id": video_id,
                        "title": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "duration": 0
                    })
                    video_ids.append(video_id)

            if video_ids:
                try:
                    details_request = youtube.videos().list(
                        part="contentDetails",
                        id=','.join(video_ids)
                    )
                    details_response = details_request.execute()
                    duration_map = {
                        item["id"]: _parse_iso8601_duration(item["contentDetails"]["duration"])
                        for item in details_response.get("items", [])
                        if item.get("contentDetails")
                    }
                    for res in results:
                        res["duration"] = duration_map.get(res["id"], 0)
                except Exception as exc:
                    logger.warning(f"Could not fetch video durations: {exc}")
            return results
        except Exception as e:
            logger.error(f"YouTube API search error: {e}")
            # Agar API limit tugasa yoki xato bo'lsa, yt-dlp ga o'tish
            return _search_yt_dlp_sync(query, max_results)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_api)


def _search_yt_dlp_sync(query: str, max_results: int = 10):
    """yt-dlp orqali sinxron qidiruv (zaxira)."""
    cookie_path = get_cookies_path()
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "noplaylist": True,
        "no_warnings": True,
        "extractor_args": build_youtube_profile().get("extractor_args", {}),
    }
    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            entries = info.get("entries", []) if info else []
            results = []
            for item in entries:
                if not isinstance(item, dict):
                    continue
                video_id = item.get("id")
                if not video_id and item.get("webpage_url"):
                    video_id = item["webpage_url"].split("v=")[-1]
                results.append({
                    "id": video_id,
                    "title": item.get("title", "Unknown Title"),
                    "url": item.get("webpage_url", ""),
                    "duration": item.get("duration", 0) or 0,
                })
            return results
    except Exception as e:
        logger.error(f"yt-dlp search error: {e}")
        return []


async def _search_yt_dlp(query: str, max_results: int = 10):
    """yt-dlp orqali asinxron qidiruv (zaxira)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _search_yt_dlp_sync(query, max_results))


async def download_media(url: str, chat_id: int, audio_only: bool = True):
    """Media (YouTube, TikTok, Instagram) yuklab olish."""
    import re
    
    # URL ni tozalab olish (agar matn aralash bo'lsa)
    url_match = re.search(r'(https?://[^\s\a\b]+)', url)
    if url_match:
        url = url_match.group(1).replace("\\n", "").strip()
    
    file_id = f"{chat_id}_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(DOWNLOAD_DIR, file_id)
    outtmpl = f"{file_path}.%(ext)s"

    opts = get_yt_dlp_opts(outtmpl, audio_only)

    def _download_with_opts(current_opts):
        with yt_dlp.YoutubeDL(current_opts) as ydl:
            _info = ydl.extract_info(url, download=True)
            final_filename = ydl.prepare_filename(_info)

            if audio_only:
                base_path = os.path.splitext(final_filename)[0]
                mp3_path = base_path + ".mp3"
                if os.path.exists(mp3_path):
                    return _info, mp3_path

            return _info, final_filename

    def _extract_info():
        info_opts = {
            "quiet": True,
            "no_warnings": True,
            "extractor_args": opts.get("extractor_args", {}),
            "ignoreerrors": False,
            "no_color": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "allow_unplayable_formats": True,
        }
        cookie_path = get_cookies_path()
        if cookie_path:
            info_opts["cookiefile"] = cookie_path
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _pick_format_id(info):
        formats = info.get("formats") or []
        if not formats:
            return None
        if audio_only:
            audio_formats = [f for f in formats if f.get("acodec") and f.get("acodec") != "none"]
            if not audio_formats:
                return None
            audio_formats.sort(
                key=lambda f: (
                    f.get("abr") or f.get("tbr") or 0,
                    f.get("filesize") or f.get("filesize_approx") or 0,
                ),
                reverse=True,
            )
            return audio_formats[0].get("format_id")
        formats.sort(
            key=lambda f: (
                f.get("height") or 0,
                f.get("tbr") or 0,
            ),
            reverse=True,
        )
        return formats[0].get("format_id")

    def _download():
        try:
            return _download_with_opts(opts)
        except Exception as e:
            msg = str(e)
            if "Requested format is not available" in msg and audio_only:
                try:
                    info = _extract_info()
                    format_id = _pick_format_id(info) if info else None
                    if format_id:
                        direct_opts = dict(opts)
                        direct_opts["format"] = format_id
                        direct_opts["allow_unplayable_formats"] = True
                        direct_opts.pop("format_sort", None)
                        return _download_with_opts(direct_opts)
                except Exception as e_info:
                    msg = str(e_info)
                fallback_variants = [
                    {
                        "format": "bestaudio[ext=m4a]/bestaudio/best",
                        "extractor_args": {"youtube": {"player_client": ["web"]}},
                    },
                    {
                        "format": "140/251/bestaudio/best",
                        "extractor_args": {"youtube": {"player_client": ["web"]}},
                    },
                    {
                        "format": "bestaudio/best",
                        "extractor_args": {"youtube": {"player_client": ["web"]}},
                    },
                    {
                        "format": "best",
                        "extractor_args": {"youtube": {"player_client": ["web"]}},
                    },
                    {
                        "format": "best",
                        "extractor_args": {},
                    },
                ]

                for variant in fallback_variants:
                    fallback_opts = dict(opts)
                    fallback_opts.update(variant)
                    fallback_opts.pop("format_sort", None)
                    fallback_opts["allow_unplayable_formats"] = True
                    try:
                        return _download_with_opts(fallback_opts)
                    except Exception as e2:
                        msg = str(e2)
            if "Sign in to confirm" in msg or "bot" in msg.lower():
                msg = (
                    "YouTube bot tekshiruvi: cookie muammosi yoki IP bloklangan. "
                    "Iltimos cookie ni yangilang yoki keyinroq urinib ko'ring."
                )
            elif "format is not available" in msg or "Requested format is not available" in msg:
                msg = (
                    "Ushbu audio uchun format topilmadi. Ba'zi videolar YouTube tomonidan "
                    "cheklangan bo'ladi — YOUTUBE_PO_TOKEN qo'shib ko'ring yoki boshqa link yuboring."
                )
            logger.error(f"Download error for {url}: {e}")
            raise Exception(msg)

    loop = asyncio.get_event_loop()
    async with _download_sem:
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

    # 50 MB limitini tekshirish (faqat audio bo'lsa)
    if audio_only and os.path.exists(final_path):
        final_path = await compress_audio(final_path)

    return info, final_path
