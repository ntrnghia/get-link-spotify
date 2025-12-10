"""File-based caching with TTL expiration and batch writes."""

import atexit
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import CACHE_BATCH_SIZE, PROXY_CACHE_FILE, PROXY_CACHE_TTL_MINUTES, SPOTIFY_CACHE_FILE, SPOTIFY_CACHE_TTL_HOURS


class FileCache:
    """Thread-safe JSON file cache with TTL and batch writes."""

    def __init__(self, cache_file: Path, ttl_minutes: int, batch_size: int = CACHE_BATCH_SIZE):
        self.cache_file, self.ttl = cache_file, timedelta(minutes=ttl_minutes)
        self.batch_size = batch_size
        self._lock, self._cache, self._pending = threading.Lock(), {}, 0
        self._load()
        atexit.register(self.flush)

    def _load(self) -> None:
        if self.cache_file.exists():
            try:
                self._cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save(self) -> None:
        try:
            self.cache_file.write_text(json.dumps(self._cache, indent=2, ensure_ascii=False), encoding="utf-8")
        except IOError:
            pass

    def _expired(self, cached_at: str) -> bool:
        try:
            return datetime.now() > datetime.fromisoformat(cached_at) + self.ttl
        except (ValueError, TypeError):
            return True

    def get(self, key: str) -> Any | None:
        with self._lock:
            if (entry := self._cache.get(key)) and not self._expired(entry.get("cached_at", "")):
                return entry.get("value")
            if entry:
                del self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._cache[key] = {"value": value, "cached_at": datetime.now().isoformat()}
            self._pending += 1
            if self._pending >= self.batch_size:
                self._save()
                self._pending = 0

    def flush(self) -> None:
        with self._lock:
            if self._pending > 0:
                self._save()
                self._pending = 0

    def remove(self, key: str) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._save()

    def clear(self) -> None:
        with self._lock:
            self._cache = {}
            self._save()

    def keys(self) -> list[str]:
        with self._lock:
            return [k for k, v in self._cache.items() if not self._expired(v.get("cached_at", ""))]


class SpotifyCache(FileCache):
    """Cache for Spotify search results."""
    def __init__(self):
        super().__init__(SPOTIFY_CACHE_FILE, SPOTIFY_CACHE_TTL_HOURS * 60)

    @staticmethod
    def _key(song_name: str, artist: str) -> str:
        return f"{song_name.lower().strip()}|{artist.lower().strip()}"

    def get_song(self, song_name: str, artist: str) -> dict | None:
        return self.get(self._key(song_name, artist))

    def set_song(self, song_name: str, artist: str, result: dict) -> None:
        self.set(self._key(song_name, artist), result)


class ProxyCache(FileCache):
    """Cache for working proxies."""
    def __init__(self):
        super().__init__(PROXY_CACHE_FILE, PROXY_CACHE_TTL_MINUTES)

    def get_working_proxies(self) -> list[dict]:
        proxies = []
        for key in self.keys():
            if (value := self.get(key)):
                ip, port = key.split(":", 1)
                proxies.append({"ip": ip, "port": port, "speed": value.get("speed_ms", 9999), "source": "cache"})
        return sorted(proxies, key=lambda p: p["speed"])

    def add_working_proxy(self, ip: str, port: str, speed_ms: int) -> None:
        self.set(f"{ip}:{port}", {"speed_ms": speed_ms})

    def remove_proxy(self, ip: str, port: str) -> None:
        self.remove(f"{ip}:{port}")


# Global instances (lazy)
_spotify_cache: SpotifyCache | None = None
_proxy_cache: ProxyCache | None = None


def get_spotify_cache() -> SpotifyCache:
    global _spotify_cache
    if _spotify_cache is None:
        _spotify_cache = SpotifyCache()
    return _spotify_cache


def get_proxy_cache() -> ProxyCache:
    global _proxy_cache
    if _proxy_cache is None:
        _proxy_cache = ProxyCache()
    return _proxy_cache


def clear_all_caches() -> None:
    get_spotify_cache().clear()
    get_proxy_cache().clear()
