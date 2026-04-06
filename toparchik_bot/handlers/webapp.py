import logging
from aiohttp import web
from urllib.parse import unquote_plus
from toparchik_bot.services.archive import archive_service

logger = logging.getLogger(__name__)

def _safe_int(value, default=0):
    try: return int(value)
    except: return default

def _serialize_song(item: dict) -> dict:
    if not isinstance(item, dict): return {}
    return {
        "id": item.get("id") or "",
        "title": item.get("title") or "Unknown",
        "duration": _safe_int(item.get("duration") or 0),
        "file_id": item.get("file_id"),
        "artist": item.get("artist") or "",
        "download_count": _safe_int(item.get("download_count") or 0),
        "play_count": _safe_int(item.get("play_count") or 0),
        "platform": item.get("platform") or "",
        "playable": bool(item.get("file_id")),
    }

def _serialize_song_list(items: list, limit: int = 50) -> list:
    if not items: return []
    return [_serialize_song(item) for item in items[:limit] if item]

async def handle_api_top(request):
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_top_songs(limit=limit)
    return web.json_response({"items": _serialize_song_list(songs, limit)})

async def handle_api_platform(request):
    platform = request.match_info.get("platform", "").lower()
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_top_songs_by_platform(platform, limit=limit)
    return web.json_response({"items": _serialize_song_list(songs, limit)})

async def handle_api_artists(request):
    artists = archive_service.get_artist_stats()
    return web.json_response({"items": artists})

async def handle_api_artist(request):
    artist = unquote_plus(request.match_info.get("artist", ""))
    limit = _safe_int(request.query.get("limit"), 200)
    songs = archive_service.get_songs_by_artist(artist)[:limit]
    return web.json_response({"items": _serialize_song_list(songs, limit)})

async def handle_api_search(request):
    query = request.query.get("q", "").strip()
    limit = _safe_int(request.query.get("limit"), 50)
    if not query:
        return web.json_response({"items": []})
    results = archive_service.search_cache(query)
    return web.json_response({"items": _serialize_song_list(results, limit)})
