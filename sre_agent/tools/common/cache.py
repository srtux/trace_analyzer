"""Thread-safe cache to prevent duplicate API calls."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


class DataCache:
    """
    Thread-safe cache to prevent duplicate API calls.

    This cache stores data with TTL (time-to-live) expiration.
    It's designed to eliminate redundant API calls when multiple sub-agents
    request the same data during parallel analysis.

    The cache is particularly important in parallel architectures
    where multiple agents may need the same data simultaneously.

    Thread Safety:
        All operations use a threading.Lock to ensure thread-safe access.

    Memory Management:
        Expired entries are automatically removed during get() operations.

    Example:
        >>> cache = DataCache(ttl_seconds=300)
        >>> cache.put("trace123", '{"trace_id": "trace123", "spans": [...]}')
        >>> data = cache.get("trace123")  # Returns cached data
        >>> data = cache.get("trace999")  # Returns None (not found)
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the data cache.

        Args:
            ttl_seconds: Time-to-live for cached entries in seconds.
                        Default is 300 seconds (5 minutes).
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds
        logger.info(f"DataCache initialized with TTL={ttl_seconds}s")

    def get(self, key: str) -> Any | None:
        """
        Get cached data if available and not expired.

        This method automatically removes expired entries during lookup.

        Args:
            key: The cache key to look up.

        Returns:
            The cached data, or None if not found or expired.
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry:
                if datetime.now(timezone.utc) < entry["expires"]:
                    logger.debug(f"Cache HIT for key {key}")
                    return entry["data"]
                else:
                    # Entry expired, remove it
                    logger.debug(f"Cache EXPIRED for key {key}")
                    del self._cache[key]
                    return None
            else:
                logger.debug(f"Cache MISS for key {key}")
                return None

    def put(self, key: str, data: Any):
        """
        Cache data with expiration.

        Args:
            key: The cache key.
            data: The data to cache.
        """
        with self._lock:
            self._cache[key] = {
                "data": data,
                "expires": datetime.now(timezone.utc)
                + timedelta(seconds=self.ttl_seconds),
                "cached_at": datetime.now(timezone.utc),
            }
            logger.debug(f"Cached key {key} (TTL={self.ttl_seconds}s)")

    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared ({count} entries removed)")

    def size(self) -> int:
        """
        Get the number of cached entries.

        Note: This includes both valid and expired entries.
        Expired entries are only removed during get() operations.

        Returns:
            The number of cached entries.
        """
        with self._lock:
            return len(self._cache)

    def stats(self) -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics including:
            - total_entries: Total number of cached entries
            - expired_entries: Number of expired entries
            - active_entries: Number of active (non-expired) entries
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            total = len(self._cache)
            expired = sum(
                1 for entry in self._cache.values() if now >= entry["expires"]
            )
            active = total - expired

            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": active,
                "ttl_seconds": self.ttl_seconds,
            }


# Global singleton instance
_data_cache = DataCache()


def get_data_cache() -> DataCache:
    """
    Get the global data cache instance.

    This function provides access to the singleton DataCache instance
    used throughout the application.

    Returns:
        The global DataCache instance.

    Example:
        >>> from sre_agent.tools.common.cache import get_data_cache
        >>> cache = get_data_cache()
        >>> cache.put("key123", data)
    """
    return _data_cache
