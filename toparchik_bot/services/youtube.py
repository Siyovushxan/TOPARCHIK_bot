import asyncio
import time
import base64
import os
import re
import logging
import yt_dlp
from urllib.parse import unquote
from googleapiclient.discovery import build
from toparchik_bot.config import (
    DOWNLOAD_DIR,
    DOWNLOAD_CONCURRENCY,
    YOUTUBE_COOKIES,
    YOUTUBE_COOKIES_B64,
    YOUTUBE_COOKIES_PATH,
    YOUTUBE_PO_TOKEN,
    YOUTUBE_VISITOR_DATA,
    YOUTUBE_API_KEY,
    YTDLP_PROXY,
    YTDLP_FORCE_IPV4,
    YTDLP_BLOCK_TTL_SEC
)

logger = logging.getLogger(__name__)
_cookie_warning_emitted = False
_download_sem = asyncio.Semaphore(max(1, DOWNLOAD_CONCURRENCY))
_blocked_until: dict[str, float] = {}


def _warn_once(message: str):
    global _cookie_warning_emitted
    if not _cookie_warning_emitted:
        logger.warning(message)
        _cookie_warning_emitted = True


def get_cookies_path():
    """Cookie faylini tayyorlaydi - hozir ishlatilmaydi."""
    return None


def build_youtube_profile() -> dict:
    """yt-dlp uchun YouTube extractor argumentlari.
    
    ios va android clientlari serverlarda bloklanish ehtimoli ancha past.
    """
    youtube_args: dict = {
        "player_client": ["web", "android_music", "ios", "android", "mweb", "tv_embedded"],
        "include_dash_manifest": True,
        "include_hls_manifest": True,
    }
    if YTDLP_FORCE_IPV4:
        youtube_args["force_ipv4"] = True
    
    def _parse_po_tokens(raw_value: str) -> list[str]:
        tokens = [t.strip() for t in raw_value.split(",") if t.strip()]
        expanded: list[str] = []
        for token in tokens:
            # If token already specifies a client (e.g. web.gvs+TOKEN, web.player+TOKEN), keep it.
            if "+" in token:
                expanded.append(token)
                continue
            # Default fallback: attach to common clients.
            expanded.append(f"web+{token}")
            expanded.append(f"ios+{token}")
        # Deduplicate while preserving order
        seen = set()
        result = []
        for token in expanded:
            if token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result

    # PO Token va Visitor Data ni formatlash
    if YOUTUBE_PO_TOKEN:
        youtube_args["po_token"] = _parse_po_tokens(YOUTUBE_PO_TOKEN)
        # PO token bo'lsa ham boshqa clientlarni saqlab qolamiz
        if "web" not in youtube_args["player_client"]:
            youtube_args["player_client"].insert(0, "web")
    
    if YOUTUBE_VISITOR_DATA:
        visitor_data = YOUTUBE_VISITOR_DATA.strip()
        if "%" in visitor_data:
            try:
                visitor_data = unquote(visitor_data)
            except Exception:
                pass
        youtube_args["visitor_data"] = [visitor_data]
        
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
    """yt-dlp uchun minimal va tezkor parametrlar."""
    
    opts = {
        "outtmpl": outtmpl,
        "quiet": False,
        "noprogress": True,
        "no_warnings": False,
        "socket_timeout": 10,
        "ratelimit": 1000000,
        "ignoreerrors": False,
        "no_color": True,
        "skip_unavailable_fragments": True,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "postprocessor_args": {
            "ffmpeg": ["-threads", "0", "-preset", "veryfast"]
        },
    }

    if YTDLP_PROXY:
        opts["proxy"] = YTDLP_PROXY

    if audio_only:
        opts.update({
            "format": "140/251/250/18/22/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts.update({
            "format": "18/22/best",
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
    if YTDLP_PROXY:
        ydl_opts["proxy"] = YTDLP_PROXY
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

    # Skip temporarily blocked videos to avoid repeated failures
    video_id_match = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})', url)
    vid = video_id_match.group(1) if video_id_match else None
    if vid:
        now = time.monotonic()
        blocked_until = _blocked_until.get(vid)
        if blocked_until and blocked_until > now:
            raise Exception("Bu video vaqtincha bloklangan. Keyinroq urinib ko'ring.")
    
    file_id = f"{chat_id}_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(DOWNLOAD_DIR, file_id)
    outtmpl = f"{file_path}.%(ext)s"

    opts = get_yt_dlp_opts(outtmpl, audio_only)

    def _download_with_opts(current_opts, target_url: str | None = None):
        with yt_dlp.YoutubeDL(current_opts) as ydl:
            _info = ydl.extract_info(target_url or url, download=True)
            final_filename = ydl.prepare_filename(_info)

            if audio_only:
                base_path = os.path.splitext(final_filename)[0]
                mp3_path = base_path + ".mp3"
                if os.path.exists(mp3_path):
                    return _info, mp3_path

            return _info, final_filename

    def _extract_info(extractor_args_override: dict | None = None):
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
        if extractor_args_override is not None:
            info_opts["extractor_args"] = extractor_args_override
        cookie_path = get_cookies_path()
        if cookie_path:
            info_opts["cookiefile"] = cookie_path
            if "youtube" in info_opts["extractor_args"] and "visitor_data" in info_opts["extractor_args"]["youtube"]:
                info_opts["extractor_args"] = dict(info_opts["extractor_args"])
                info_opts["extractor_args"]["youtube"] = dict(info_opts["extractor_args"]["youtube"])
                info_opts["extractor_args"]["youtube"].pop("visitor_data", None)
        if YTDLP_PROXY:
            info_opts["proxy"] = YTDLP_PROXY
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
                # Simple fallback: try with minimal format selection
                try:
                    logger.info(f"Format retry for {vid}: using format 18")
                    opts_retry = dict(opts)
                    opts_retry["format"] = "18/22/best"
                    opts_retry.pop("allow_unplayable_formats", None)
                    return _download_with_opts(opts_retry)
                except Exception as e_retry:
                    msg = str(e_retry)
                    
            if "Sign in to confirm" in msg or "bot" in msg.lower():
                msg = "YouTube bot tekshiruvi: cookie muammosi. Keyinroq urinib ko'ring."
            elif "format is not available" in msg or "Requested format is not available" in msg:
                msg = (
                    "⚠️ Bu video yuklana olmadi. Lekin xavotir olmang:\n\n"
                    "✅ Boshqa YouTube linkni yuboring.\n"
                    "🎵 Savangiz saqlangan bo'lsa, arxivdan chiqar olamiz."
                )
            # Mark video as blocked to reduce noisy retries
            if vid and YTDLP_BLOCK_TTL_SEC > 0:
                _blocked_until[vid] = time.monotonic() + YTDLP_BLOCK_TTL_SEC
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
