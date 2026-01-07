"""Thread-safe cache to prevent duplicate Cloud Trace API calls."""

import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class TraceCache:
    """
    Thread-safe cache to prevent duplicate API calls.

    This cache stores trace data with TTL (time-to-live) expiration.
    It's designed to eliminate redundant API calls when multiple sub-agents
    request the same trace data during parallel analysis.

    The cache is particularly important in the two-stage parallel architecture
    where 4-5 agents may need the same trace data simultaneously.

    Thread Safety:
        All operations use a threading.Lock to ensure thread-safe access.

    Memory Management:
        Expired entries are automatically removed during get() operations.
        Consider implementing periodic cleanup for long-running processes.

    Example:
        >>> cache = TraceCache(ttl_seconds=300)
        >>> cache.put("trace123", '{"trace_id": "trace123", "spans": [...]}')
        >>> data = cache.get("trace123")  # Returns cached data
        >>> data = cache.get("trace999")  # Returns None (not found)
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the trace cache.

        Args:
            ttl_seconds: Time-to-live for cached entries in seconds.
                        Default is 300 seconds (5 minutes).
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.ttl_seconds = ttl_seconds
        logger.info(f"TraceCache initialized with TTL={ttl_seconds}s")

    def get(self, trace_id: str) -> Optional[str]:
        """
        Get cached trace data if available and not expired.

        This method automatically removes expired entries during lookup.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            The cached trace data as a JSON string, or None if not found or expired.
        """
        with self._lock:
            entry = self._cache.get(trace_id)
            if entry:
                if datetime.now(timezone.utc) < entry["expires"]:
                    logger.debug(f"Cache HIT for trace {trace_id}")
                    return entry["data"]
                else:
                    # Entry expired, remove it
                    logger.debug(f"Cache EXPIRED for trace {trace_id}")
                    del self._cache[trace_id]
                    return None
            else:
                logger.debug(f"Cache MISS for trace {trace_id}")
                return None

    def put(self, trace_id: str, data: str):
        """
        Cache trace data with expiration.

        Args:
            trace_id: The trace ID to cache.
            data: The trace data as a JSON string.
        """
        with self._lock:
            self._cache[trace_id] = {
                "data": data,
                "expires": datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds),
                "cached_at": datetime.now(timezone.utc)
            }
            logger.debug(f"Cached trace {trace_id} (TTL={self.ttl_seconds}s)")

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
            The number of cached trace entries.
        """
        with self._lock:
            return len(self._cache)

    def stats(self) -> Dict[str, Any]:
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
            expired = sum(1 for entry in self._cache.values() if now >= entry["expires"])
            active = total - expired

            return {
                "total_entries": total,
                "expired_entries": expired,
                "active_entries": active,
                "ttl_seconds": self.ttl_seconds
            }


# Global singleton instance
_trace_cache = TraceCache()


def get_trace_cache() -> TraceCache:
    """
    Get the global trace cache instance.

    This function provides access to the singleton TraceCache instance
    used throughout the application.

    Returns:
        The global TraceCache instance.

    Example:
        >>> from trace_analyzer.tools.trace_cache import get_trace_cache
        >>> cache = get_trace_cache()
        >>> cache.put("trace123", trace_data)
    """
    return _trace_cache
