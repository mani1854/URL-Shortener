"""
dependencies/services.py

Composes service objects from lower-level dependencies and exposes them
as FastAPI dependency callables.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.cache import get_cache
from app.dependencies.db import get_db
from app.services.analytics_service import AnalyticsService
from app.services.url_service import URLService
from app.utils.cache import CacheClient


def get_url_service(
    db: AsyncSession = Depends(get_db),
    cache: CacheClient = Depends(get_cache),
) -> URLService:
    """
    Construct a URLService with its required dependencies.

    Usage in a route:
        async def my_route(svc: URLService = Depends(get_url_service)): ...
    """
    return URLService(db=db, cache=cache)


def get_analytics_service(
    db: AsyncSession = Depends(get_db),
) -> AnalyticsService:
    """
    Construct an AnalyticsService instance with database session.

    Usage in a route:
        async def my_route(svc: AnalyticsService = Depends(get_analytics_service)): ...
    """
    return AnalyticsService(db=db)
