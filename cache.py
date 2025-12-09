"""
File-based caching for Spotify searches and working proxies.
Stores JSON files in project root for cross-run persistence.
Uses batch writes to reduce disk I/O.
"""

import atexit
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from config import (
    CACHE_BATCH_SIZE,
    PROXY_CACHE_FILE,
    PROXY_CACHE_TTL_MINUTES,
    SPOTIFY_CACHE_FILE,
    SPOTIFY_CACHE_TTL_HOURS,
)


class FileCache:
    """Thread-safe JSON file cache with TTL expiration and batch writes."""

    def __init__(self, cache_file: Path, ttl_minutes: int, batch_size: int = CACHE_BATCH_SIZE):
        self.cache_file = cache_file
        self.ttl_minutes = ttl_minutes
        self.batch_size = batch_size
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._pending_writes = 0
        self._load()
        # Register flush on exit to ensure all data is saved
        atexit.register(self.flush)

    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}

    def _save(self) -> None:
        """Save cache to disk (must hold lock)."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except IOError:
            pass  # Silently fail on write errors

    def _is_expired(self, cached_at: str) -> bool:
        """Check if cache entry is expired."""
        try:
            cached_time = datetime.fromisoformat(cached_at)
            expiry = cached_time + timedelta(minutes=self.ttl_minutes)
            return datetime.now() > expiry
        except (ValueError, TypeError):
            return True

    def get(self, key: str) -> Any | None:
        """Get value from cache, returns None if missing or expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if self._is_expired(entry.get("cached_at", "")):
                del self._cache[key]
                return None
            return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp (batched writes)."""
        with self._lock:
            self._cache[key] = {
                "value": value,
                "cached_at": datetime.now().isoformat(),
            }
            self._pending_writes += 1
            if self._pending_writes >= self.batch_size:
                self._save()
                self._pending_writes = 0

    def flush(self) -> None:
        """Force save all pending writes to disk."""
        with self._lock:
            if self._pending_writes > 0:
                self._save()
                self._pending_writes = 0

    def get_with_metadata(self, key: str) -> tuple[Any | None, str | None]:
        """Get value and cached_at timestamp, returns (None, None) if missing/expired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None, None
            if self._is_expired(entry.get("cached_at", "")):
                del self._cache[key]
                return None, None
            return entry.get("value"), entry.get("cached_at")

    def clear_expired(self) -> int:
        """Remove all expired entries, returns count of removed entries."""
        with self._lock:
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if self._is_expired(entry.get("cached_at", ""))
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                self._save()
            return len(expired_keys)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache = {}
            self._save()

    def keys(self) -> list[str]:
        """Get all valid (non-expired) cache keys."""
        with self._lock:
            return [
                key
                for key, entry in self._cache.items()
                if not self._is_expired(entry.get("cached_at", ""))
            ]

    def __len__(self) -> int:
        """Return count of valid (non-expired) entries."""
        with self._lock:
            return sum(
                1 for entry in self._cache.values()
                if not self._is_expired(entry.get("cached_at", ""))
            )

    def stats(self) -> dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            total = len(self._cache)
            valid = sum(
                1 for entry in self._cache.values()
                if not self._is_expired(entry.get("cached_at", ""))
            )
            return {"total": total, "valid": valid, "expired": total - valid}


class SpotifyCache(FileCache):
    """Cache for Spotify search results."""

    def __init__(self):
        super().__init__(
            SPOTIFY_CACHE_FILE,
            ttl_minutes=SPOTIFY_CACHE_TTL_HOURS * 60,
        )

    @staticmethod
    def make_key(song_name: str, artist: str) -> str:
        """Create cache key from song name and artist."""
        return f"{song_name.lower().strip()}|{artist.lower().strip()}"

    def get_song(self, song_name: str, artist: str) -> dict | None:
        """Get cached Spotify result for a song."""
        key = self.make_key(song_name, artist)
        return self.get(key)

    def set_song(self, song_name: str, artist: str, spotify_result: dict) -> None:
        """Cache Spotify result for a song."""
        key = self.make_key(song_name, artist)
        self.set(key, spotify_result)


class ProxyCache(FileCache):
    """Cache for working proxies."""

    def __init__(self):
        super().__init__(
            PROXY_CACHE_FILE,
            ttl_minutes=PROXY_CACHE_TTL_MINUTES,
        )

    @staticmethod
    def make_key(ip: str, port: str) -> str:
        """Create cache key from proxy IP and port."""
        return f"{ip}:{port}"

    def get_working_proxies(self) -> list[dict]:
        """Get all cached working proxies, sorted by speed."""
        proxies = []
        for key in self.keys():
            value = self.get(key)
            if value:
                ip, port = key.split(":", 1)
                proxies.append({
                    "ip": ip,
                    "port": port,
                    "speed": value.get("speed_ms", 9999),
                    "source": "cache",
                })
        return sorted(proxies, key=lambda p: p["speed"])

    def add_working_proxy(self, ip: str, port: str, speed_ms: int) -> None:
        """Add a working proxy to cache."""
        key = self.make_key(ip, port)
        self.set(key, {"speed_ms": speed_ms})

    def remove_proxy(self, ip: str, port: str) -> None:
        """Remove a proxy from cache."""
        key = self.make_key(ip, port)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._save()


# Global cache instances (lazy initialization)
_spotify_cache: SpotifyCache | None = None
_proxy_cache: ProxyCache | None = None


def get_spotify_cache() -> SpotifyCache:
    """Get or create Spotify cache instance."""
    global _spotify_cache
    if _spotify_cache is None:
        _spotify_cache = SpotifyCache()
    return _spotify_cache


def get_proxy_cache() -> ProxyCache:
    """Get or create proxy cache instance."""
    global _proxy_cache
    if _proxy_cache is None:
        _proxy_cache = ProxyCache()
    return _proxy_cache


def clear_all_caches() -> None:
    """Clear both caches (for benchmarking)."""
    get_spotify_cache().clear()
    get_proxy_cache().clear()
