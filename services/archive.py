import json
import os
from config import CACHE_FILE, ARCHIVE_CHANNEL

class ArchiveService:
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

    def cache_file_info(self, unique_id: str, file_id: str, title: str, duration: float):
        """Stores the Telegram file_id and metadata in the cache."""
        self.cache[unique_id] = {
            "file_id": file_id,
            "title": title,
            "duration": duration
        }
        self.save_cache()

    def search_cache(self, query: str) -> list:
        """Independently search by all keywords in the query to make it 'smart'."""
        keywords = query.lower().split()
        results = []
        for vid, data in self.cache.items():
            if isinstance(data, dict):
                title_lower = data.get("title", "").lower()
                # Check if ALL keywords exist in the title
                if all(kw in title_lower for kw in keywords):
                    results.append({
                        "id": vid,
                        "title": data.get("title", ""),
                        "duration": data.get("duration", 0),
                        "file_id": data.get("file_id")
                    })
        return results

# Global instance
archive_service = ArchiveService()
