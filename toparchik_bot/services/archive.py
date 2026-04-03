import json
import os
from toparchik_bot.config import CACHE_FILE, ARCHIVE_CHANNEL

class ArchiveService:
        def get_top_songs(self, limit=10):
            """Eng ko'p yuklangan (arxivda eng ko'p uchraydigan yoki oxirgi qo'shilgan) qo'shiqlar ro'yxati."""
            # Agar cache da yuklash soni bo'lsa, shunga qarab saralaymiz, aks holda oxirgi qo'shilganlar
            # Hozircha oddiy: oxirgi qo'shilganlar (dict insertion order Python 3.7+)
            songs = [
                {"id": vid, **data}
                for vid, data in self.cache.items() if isinstance(data, dict)
            ]
            # Agar yuklash soni bo'lsa, shunga qarab saralash mumkin (future)
            # Hozircha oxirgi qo'shilganlar
            return list(reversed(songs))[:limit]

        def get_top_songs_by_platform(self, platform, limit=10):
            """Platforma bo'yicha eng ko'p yuklangan qo'shiqlar (YouTube, TikTok, Instagram)."""
            platform = platform.lower()
            songs = []
            for vid, data in self.cache.items():
                if not isinstance(data, dict):
                    continue
                title = data.get("title", "").lower()
                # Oddiy heuristika: title yoki id orqali platformani aniqlash
                if platform == "youtube" and ("youtube" in title or len(vid) == 11):
                    songs.append({"id": vid, **data})
                elif platform == "tiktok" and ("tiktok" in title):
                    songs.append({"id": vid, **data})
                elif platform == "instagram" and ("instagram" in title):
                    songs.append({"id": vid, **data})
            return list(reversed(songs))[:limit]
    def __init__(self):
        self.cache = self._load_cache()

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE):
            return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"Archive cache load error: {exc}")
            return {}

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

    def cache_file_info(self, unique_id: str, file_id: str, title: str, duration: float, artist: str = ""):
        """Stores the Telegram file_id and metadata in the cache."""
        if not artist:
            artist = self._extract_artist_from_title(title)
        self.cache[unique_id] = {
            "file_id": file_id,
            "title": title,
            "duration": duration,
            "artist": artist.strip()
        }
        self.save_cache()

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
                        "file_id": data.get("file_id")
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
                        "file_id": data.get("file_id")
                    })
        return results

# Global instance
archive_service = ArchiveService()
