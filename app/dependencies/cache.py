"""
dependencies/cache.py

FastAPI dependency for injecting a CacheClient (Redis wrapper).
"""

from __future__ import annotations

from app.utils.cache import CacheClient, _redis_client


def get_cache() -> CacheClient:
    """
    Inject an application-level CacheClient backed by the global Redis pool (or in-memory cache).

    Usage in a route:
        async def my_route(cache: CacheClient = Depends(get_cache)): ...
    """
    return CacheClient(_redis_client)
