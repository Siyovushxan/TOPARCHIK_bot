import json
import os
import logging
from toparchik_bot.config import CACHE_FILE

logger = logging.getLogger(__name__)

try:
    from google.cloud import firestore
    # Auto-detect project ID from environment in Cloud Run/Functions
    db = firestore.Client()
    COLLECTION_NAME = "songs_archive"
    USE_FIRESTORE = True
    logger.info("Firestore client initialized for ArchiveService.")
except Exception as e:
    logger.warning(f"Firestore initialization failed (falling back to JSON): {e}")
    USE_FIRESTORE = False

class ArchiveService:
    def __init__(self):
        self.cache = {}
        if not USE_FIRESTORE:
            self.cache = self._load_cache()
            self._normalize_cache()
        else:
            # In Firestore mode, we don't hold the entire cache in memory 
            # for every operation, but we might want to sync once if JSON exists.
            if os.path.exists(CACHE_FILE):
                self._migrate_json_to_firestore()

    def _migrate_json_to_firestore(self):
        """One-time migration from JSON to Firestore."""
        try:
            local_data = self._load_cache()
            if not local_data: return
            
            logger.info(f"Migrating {len(local_data)} items from JSON to Firestore...")
            batch = db.batch()
            count = 0
            for vid, data in local_data.items():
                if not isinstance(data, dict): continue
                doc_ref = db.collection(COLLECTION_NAME).document(vid)
                batch.set(doc_ref, data)
                count += 1
                if count % 400 == 0:
                    batch.commit()
                    batch = db.batch()
            batch.commit()
            logger.info("Migration completed. Deleting local CACHE_FILE.")
            os.remove(CACHE_FILE)
        except Exception as e:
            logger.error(f"Migration failed: {e}")

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE): return {}
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error(f"Archive cache load error: {exc}")
            return {}

    def _normalize_cache(self):
        changed = False
        for key, value in list(self.cache.items()):
            if isinstance(value, str):
                self.cache[key] = {
                    "file_id": value, "title": "", "duration": 0, "artist": "",
                    "download_count": 0, "play_count": 0, "platform": ""
                }
                changed = True
        if changed: self.save_cache()

    def save_cache(self):
        if USE_FIRESTORE: return # Firestore handles its own saving
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error(f"Archive cache save error: {exc}")

    def get_top_songs(self, limit=10):
        if USE_FIRESTORE:
            docs = db.collection(COLLECTION_NAME).order_by("download_count", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [{"id": d.id, **d.to_dict()} for d in docs]
        
        songs = self._as_song_list()
        songs.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return songs[:limit]

    def get_top_songs_by_platform(self, platform, limit=10):
        platform = platform.lower()
        if USE_FIRESTORE:
            docs = db.collection(COLLECTION_NAME).where("platform", "==", platform).order_by("download_count", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [{"id": d.id, **d.to_dict()} for d in docs]
            
        songs = [s for s in self._as_song_list() if (s.get("platform") or "").lower() == platform]
        songs.sort(key=lambda s: (-s.get("download_count", 0), s.get("title", "")))
        return songs[:limit]

    def _as_song_list(self):
        return [{"id": vid, **data} for vid, data in self.cache.items() if isinstance(data, dict)]

    def get_cached_file_id(self, unique_id: str) -> str:
        if USE_FIRESTORE:
            doc = db.collection(COLLECTION_NAME).document(unique_id).get()
            return doc.to_dict().get("file_id") if doc.exists else None
        return self.cache.get(unique_id, {}).get("file_id") if isinstance(self.cache.get(unique_id), dict) else None

    def cache_file_info(self, unique_id: str, file_id: str, title: str, duration: float, artist: str = "", platform: str = ""):
        data = {
            "file_id": file_id,
            "title": title,
            "duration": duration,
            "artist": artist.strip(),
            "platform": platform,
            "download_count": firestore.Increment(0) if USE_FIRESTORE else 0,
            "play_count": firestore.Increment(0) if USE_FIRESTORE else 0
        }
        if USE_FIRESTORE:
            db.collection(COLLECTION_NAME).document(unique_id).set(data, merge=True)
        else:
            self.cache[unique_id] = data
            self.save_cache()

    def increment_download(self, unique_id: str):
        if USE_FIRESTORE:
            db.collection(COLLECTION_NAME).document(unique_id).update({"download_count": firestore.Increment(1)})
        else:
            data = self.cache.get(unique_id)
            if data:
                data["download_count"] = data.get("download_count", 0) + 1
                self.save_cache()

    def search_cache(self, query: str) -> list:
        # Note: Firestore doesn't support complex full-text search easily without external tools.
        # But for small/medium archives, we can search by prefix or use a hybrid approach.
        # For now, let's keep search simple (case-sensitive prefix search is limited).
        # We might need to pull a subset and search in memory, or use Firestore 'array-contains' for keywords.
        if USE_FIRESTORE:
            # Very simple "contains" simulation for Firestore (limited)
            # Better way: split title into keywords and use array-contains-any
            keywords = query.lower().split()
            # If we have only 1 keyword, we can search better
            # For simplicity in this v1 migration, we'll fetch top 500 and filter in memory
            # (Firestore is much faster than JSON parsing anyway)
            docs = db.collection(COLLECTION_NAME).limit(500).stream()
            results = []
            for doc in docs:
                d = doc.to_dict()
                t = d.get("title", "").lower()
                a = d.get("artist", "").lower()
                if all(kw in t or kw in a for kw in keywords):
                    results.append({"id": doc.id, **d})
            return results

        # JSON fallback
        keywords = query.lower().split()
        return [s for s in self._as_song_list() if all(kw in s.get("title", "").lower() or kw in s.get("artist", "").lower() for kw in keywords)]

    def get_all_artists(self) -> list:
        if USE_FIRESTORE:
            # This is expensive in Firestore. Better to have a separate 'artists' collection.
            # But let's keep it simple for now.
            docs = db.collection(COLLECTION_NAME).select(["artist"]).stream()
            artists = {d.to_dict().get("artist") for d in docs if d.to_dict().get("artist")}
            return sorted(list(artists))
        
        artists = {s.get("artist") for s in self._as_song_list() if s.get("artist")}
        return sorted(list(artists))

    def get_artist_stats(self) -> list:
        # In a real app, you'd want a separate collection for artist stats.
        # For migration, we'll aggregate top 500.
        all_songs = self.get_top_songs(limit=500)
        stats = {}
        for s in all_songs:
            artist = s.get("artist", "Noma'lum ijrochi")
            info = stats.setdefault(artist, {"artist": artist, "song_count": 0, "total_downloads": 0})
            info["song_count"] += 1
            info["total_downloads"] += int(s.get("download_count", 0) or 0)
        return sorted(stats.values(), key=lambda x: -x["total_downloads"])

    def get_songs_by_artist(self, artist: str) -> list:
        if USE_FIRESTORE:
            docs = db.collection(COLLECTION_NAME).where("artist", "==", artist).order_by("download_count", direction=firestore.Query.DESCENDING).stream()
            return [{"id": d.id, **d.to_dict()} for d in docs]
        
        songs = [s for s in self._as_song_list() if s.get("artist") == artist]
        songs.sort(key=lambda s: -s.get("download_count", 0))
        return songs

# Global instance
archive_service = ArchiveService()
