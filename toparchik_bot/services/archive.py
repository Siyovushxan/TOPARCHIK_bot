import json
import os
from toparchik_bot.config import CACHE_FILE, ARCHIVE_CHANNEL


class ArchiveService:
    def __init__(self):
        self.cache = self._load_cache()
        self._normalize_cache()

    def get_top_songs(self, limit=10):
        """Eng ko'p yuklangan qo'shiqlar ro'yxati (download_count bo'yicha)."""
        songs = self._as_song_list()
        songs.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return songs[:limit]

    def get_top_songs_by_platform(self, platform, limit=10):
        """Platforma bo'yicha eng ko'p yuklangan qo'shiqlar (YouTube, TikTok, Instagram)."""
        platform = platform.lower()
        songs = []
        for vid, data in self.cache.items():
            if not isinstance(data, dict):
                continue
            item_platform = (data.get("platform") or "").lower()
            title = data.get("title", "").lower()
            if item_platform == platform:
                songs.append({"id": vid, **data})
                continue
            # Fallback heuristics
            if platform == "youtube" and ("youtube" in title or len(vid) == 11):
                songs.append({"id": vid, **data})
            elif platform == "tiktok" and ("tiktok" in title):
                songs.append({"id": vid, **data})
            elif platform == "instagram" and ("instagram" in title):
                songs.append({"id": vid, **data})

        songs.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return songs[:limit]

    def get_all_songs(self):
        songs = self._as_song_list()
        songs.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return songs

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"Archive cache load error: {exc}")
            return {}

    def _normalize_cache(self):
        """Convert legacy string entries to dicts so they appear in lists."""
        changed = False
        for key, value in list(self.cache.items()):
            if isinstance(value, str):
                self.cache[key] = {
                    "file_id": value,
                    "title": "",
                    "duration": 0,
                    "artist": "",
                    "download_count": 0,
                    "play_count": 0,
                    "platform": ""
                }
                changed = True
            elif isinstance(value, dict):
                self._default_counts(value)
        if changed:
            self.save_cache()

    @staticmethod
    def _default_counts(data: dict) -> dict:
        download_count = data.get("download_count", 0)
        play_count = data.get("play_count", 0)
        try:
            download_count = int(download_count)
        except Exception:
            download_count = 0
        try:
            play_count = int(play_count)
        except Exception:
            play_count = 0
        data["download_count"] = download_count
        data["play_count"] = play_count
        return data

    def _as_song_list(self):
        songs = []
        for vid, data in self.cache.items():
            item = self._coerce_entry(vid, data)
            if item:
                songs.append(item)
        return songs

    def _coerce_entry(self, unique_id, data):
        if isinstance(data, dict):
            item = {"id": unique_id, **data}
        elif isinstance(data, str):
            item = {
                "id": unique_id,
                "file_id": data,
                "title": "",
                "duration": 0,
                "artist": "",
                "download_count": 0,
                "play_count": 0,
                "platform": ""
            }
        else:
            return None
        self._default_counts(item)
        if not item.get("title"):
            item["title"] = f"Audio {unique_id}"
        return item

    @staticmethod
    def _normalize_artist(artist: str) -> str:
        if not artist:
            return ""
        return artist.strip().lower()

    @staticmethod
    def _extract_artist_from_title(title: str) -> str:
        if not title:
            return ""
        import re
        parts = re.split(r'[-–—:]', title, maxsplit=1)
        if len(parts) > 1 and parts[0].strip():
            return parts[0].strip()
        return ""

    def save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"Archive cache save error: {exc}")

    def get_cached_file_id(self, unique_id: str) -> str:
        """Returns the Telegram file_id if the file is cached."""
        data = self.cache.get(unique_id)
        if isinstance(data, dict):
            return data.get("file_id")
        return data

    def cache_file_info(self, unique_id: str, file_id: str, title: str, duration: float, artist: str = "", platform: str = ""):
        """Stores the Telegram file_id and metadata in the cache."""
        if not artist:
            artist = self._extract_artist_from_title(title)
        existing = self.cache.get(unique_id, {}) if isinstance(self.cache.get(unique_id), dict) else {}
        download_count = existing.get("download_count", 0)
        play_count = existing.get("play_count", 0)
        platform_value = platform or existing.get("platform", "")
        self.cache[unique_id] = {
            "file_id": file_id,
            "title": title,
            "duration": duration,
            "artist": artist.strip(),
            "download_count": download_count,
            "play_count": play_count,
            "platform": platform_value
        }
        self.save_cache()

    def _find_key_by_file_id(self, file_id: str):
        for key, data in self.cache.items():
            if isinstance(data, dict) and data.get("file_id") == file_id:
                return key
            if isinstance(data, str) and data == file_id:
                return key
        return None

    def upsert_audio_entry(self, unique_id: str, file_id: str, title: str, duration: float, artist: str = "", platform: str = "", message_id: int | None = None):
        if not artist:
            artist = self._extract_artist_from_title(title)
        existing_key = self._find_key_by_file_id(file_id) or unique_id
        existing = self.cache.get(existing_key, {}) if isinstance(self.cache.get(existing_key), dict) else {}
        download_count = existing.get("download_count", 0)
        play_count = existing.get("play_count", 0)
        platform_value = platform or existing.get("platform", "")
        entry = {
            "file_id": file_id,
            "title": title,
            "duration": duration,
            "artist": artist.strip(),
            "download_count": download_count,
            "play_count": play_count,
            "platform": platform_value
        }
        if message_id is not None:
            entry["message_id"] = message_id
        self.cache[existing_key] = entry
        self.save_cache()
        return existing_key

    def search_cache(self, query: str) -> list:
        """Independently search by all keywords in the query to make it 'smart'."""
        keywords = query.lower().split()
        results = []
        for vid, data in self.cache.items():
            if isinstance(data, dict):
                title_lower = data.get("title", "").lower()
                artist_lower = data.get("artist", "").lower()
                # Check if ALL keywords exist in the title or artist
                if all(kw in title_lower or kw in artist_lower for kw in keywords):
                    results.append({
                        "id": vid,
                        "title": data.get("title", ""),
                        "duration": data.get("duration", 0),
                        "file_id": data.get("file_id"),
                        "artist": data.get("artist", ""),
                        "download_count": data.get("download_count", 0),
                        "play_count": data.get("play_count", 0),
                        "platform": data.get("platform", "")
                    })
        return results

    def get_all_artists(self) -> list:
        artists = set()
        for data in self.cache.values():
            if isinstance(data, dict):
                artist = data.get("artist") or self._extract_artist_from_title(data.get("title", ""))
                if artist:
                    artists.add(artist)
        return sorted(artists)

    def get_artist_stats(self) -> list:
        stats = {}
        for vid, data in self.cache.items():
            if not isinstance(data, dict):
                continue
            artist = data.get("artist") or self._extract_artist_from_title(data.get("title", ""))
            if not artist:
                continue
            artist_key = artist.strip()
            info = stats.setdefault(artist_key, {"artist": artist_key, "song_count": 0, "total_downloads": 0})
            info["song_count"] += 1
            info["total_downloads"] += int(data.get("download_count", 0) or 0)

        result = list(stats.values())
        result.sort(key=lambda x: (-x.get("total_downloads", 0), x.get("artist", "")))
        return result

    def get_songs_by_artist(self, artist: str) -> list:
        normalized = self._normalize_artist(artist)
        results = []
        for vid, data in self.cache.items():
            if isinstance(data, dict):
                item_artist = data.get("artist") or self._extract_artist_from_title(data.get("title", ""))
                if self._normalize_artist(item_artist) == normalized:
                    results.append({
                        "id": vid,
                        "title": data.get("title", ""),
                        "duration": data.get("duration", 0),
                        "file_id": data.get("file_id"),
                        "artist": data.get("artist", ""),
                        "download_count": data.get("download_count", 0),
                        "play_count": data.get("play_count", 0),
                        "platform": data.get("platform", "")
                    })
        results.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return results

    def increment_download(self, unique_id: str):
        data = self.cache.get(unique_id)
        if not isinstance(data, dict):
            return
        count = int(data.get("download_count", 0) or 0) + 1
        data["download_count"] = count
        self.cache[unique_id] = data
        self.save_cache()

    def increment_play(self, unique_id: str):
        data = self.cache.get(unique_id)
        if not isinstance(data, dict):
            return
        count = int(data.get("play_count", 0) or 0) + 1
        data["play_count"] = count
        self.cache[unique_id] = data
        self.save_cache()

# Global instance
archive_service = ArchiveService()
