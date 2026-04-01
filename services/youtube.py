import asyncio
import os
import yt_dlp
from config import DOWNLOAD_DIR, YOUTUBE_COOKIES, YOUTUBE_PO_TOKEN, YOUTUBE_VISITOR_DATA

def get_yt_dlp_opts(outtmpl: str, audio_only: bool = True) -> dict:
    opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "noprogress": True,
        "extractor_retries": 5,
        "retries": 3,
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

    # We DO NOT use YOUTUBE_COOKIES unconditionally anymore because logged-in YouTube 
    # serves modern ES6 obfuscated Javascript which js2py cannot parse, 
    # causing "Signature solving failed" errors on public music videos!
    # Cookies should only be used as a last resort for age-restricted content.
        
    return opts

def build_youtube_profile():
    # Since we have installed js2py, the default WEB client is now fully functional and fast.
    extractor_args = {}
    if YOUTUBE_PO_TOKEN:
        extractor_args = {
            "youtube": {
                "player_client": ["mweb", "web"],
                "po_token": [f"mweb.gvs+{YOUTUBE_PO_TOKEN}"],
            }
        }
        if YOUTUBE_VISITOR_DATA:
            extractor_args["youtube"]["visitor_data"] = [YOUTUBE_VISITOR_DATA]
            extractor_args["youtube"]["player_skip"] = ["configs", "webpage"]
            
    return {"name": "default", "extractor_args": extractor_args}

async def search_youtube(query: str, max_results: int = 10):
    """Async search for YouTube content."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "noplaylist": True,
        "extractor_args": build_youtube_profile().get("extractor_args", {})
    }
    
    def _search():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch{max_results}:{query}", download=False).get("entries", [])

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)

async def download_media(url: str, chat_id: int, audio_only: bool = True):
    """Async download of media (YouTube, TikTok, Instagram)."""
    file_id = f"{chat_id}_{int(asyncio.get_event_loop().time())}"
    file_path = os.path.join(DOWNLOAD_DIR, file_id)
    outtmpl = f"{file_path}.%(ext)s"
    
    opts = get_yt_dlp_opts(outtmpl, audio_only)
    if "youtube.com" in url or "youtu.be" in url:
        opts["extractor_args"] = build_youtube_profile().get("extractor_args", {})
        
    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            _info = ydl.extract_info(url, download=True)
            return _info, ydl.prepare_filename(_info)
            
    loop = asyncio.get_event_loop()
    info, final_path = await loop.run_in_executor(None, _download)
        
    if audio_only and not final_path.endswith(".mp3"):
        final_path = os.path.splitext(final_path)[0] + ".mp3"
        
    return info, final_path
