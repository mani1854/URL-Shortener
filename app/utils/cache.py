"""
utils/cache.py

Redis cache client wrapper for high-performance URL lookups and caching.
Implements the Cache-Aside pattern with a 30-minute (1800s) default TTL
and explicit cache eviction upon update or deletion of short URLs.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton for connection lifecycle
_redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create the async Redis connection pool. Called once at startup."""
    global _redis_client
    try:
        _redis_client = aioredis.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
        await _redis_client.ping()
        logger.info("Redis client connected at %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Could not connect to Redis at %s: %s (operating with degraded cache)", settings.REDIS_URL, exc)


async def close_redis() -> None:
    """Close the Redis connection pool. Called on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.debug("Redis client closed")


def get_redis() -> aioredis.Redis:
    """Return the active Redis client; raises if not initialised."""
    if _redis_client is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis_client


_memory_cache: dict[str, str] = {}


class CacheClient:
    """
    Application-level cache operations.

    Wraps raw Redis calls with:
      - Domain-aware key prefixes ("url_shortener:")
      - Standard 30-minute TTL (CACHE_TTL_SECONDS)
      - Graceful in-memory fallback when Redis is offline
    """

    PREFIX = "url_shortener:"

    def __init__(self, client: aioredis.Redis | None = None) -> None:
        self._client = client

    def _key(self, *parts: str) -> str:
        """Generate a namespaced Redis key."""
        return self.PREFIX + ":".join(parts)

    # ── Generic Redis Operations ──────────────────────────────────────────────

    async def get(self, *key_parts: str) -> str | None:
        """Fetch string value for key parts, returning None if missing or on error."""
        k = self._key(*key_parts)
        if self._client is not None:
            try:
                return await self._client.get(k)
            except Exception as exc:
                logger.warning("Cache GET failed for %s: %s", key_parts, exc)
                return None
        return _memory_cache.get(k)

    async def set(
        self,
        *key_parts: str,
        value: str,
        ttl: int = settings.CACHE_TTL_SECONDS,
    ) -> bool:
        """Cache a string value with TTL in seconds (default: 1800s / 30m)."""
        k = self._key(*key_parts)
        if self._client is not None:
            try:
                await self._client.setex(k, ttl, value)
                return True
            except Exception as exc:
                logger.warning("Cache SET failed for %s: %s", key_parts, exc)
                return False
        _memory_cache[k] = value
        return True

    async def delete(self, *key_parts: str) -> bool:
        """Evict a key from cache."""
        k = self._key(*key_parts)
        if self._client is not None:
            try:
                await self._client.delete(k)
                return True
            except Exception as exc:
                logger.warning("Cache DELETE failed for %s: %s", key_parts, exc)
                return False
        _memory_cache.pop(k, None)
        return True

    async def exists(self, *key_parts: str) -> bool:
        """Check if a key exists in cache."""
        k = self._key(*key_parts)
        if self._client is not None:
            try:
                result = await self._client.exists(k)
                return bool(result)
            except Exception as exc:
                logger.warning("Cache EXISTS failed for %s: %s", key_parts, exc)
                return False
        return k in _memory_cache

    # ── Short-URL Domain Operations ───────────────────────────────────────────

    async def get_original_url(self, short_code: str) -> str | None:
        """
        Return the cached original destination URL for a short code.
        Key format: url_shortener:short:<short_code>
        """
        return await self.get("short", short_code)

    async def set_original_url(
        self,
        short_code: str,
        original_url: str,
        ttl: int = settings.CACHE_TTL_SECONDS,
    ) -> bool:
        """
        Cache mapping of short_code -> original_url for 30 minutes (1800s).
        """
        return await self.set("short", short_code, value=original_url, ttl=ttl)

    async def evict_short_code(self, short_code: str) -> bool:
        """
        Invalidate a short code from cache upon update or deletion.
        """
        return await self.delete("short", short_code)
