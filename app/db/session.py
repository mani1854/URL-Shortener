"""
db/session.py

Async SQLAlchemy engine and session factory.
The engine is created once at startup (via init_db) and torn down on
shutdown (via close_db).  All request-scoped sessions are created by the
get_db dependency in app/dependencies/db.py.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level singletons (populated by init_db / close_db)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create the async engine and session factory. Called once at startup."""
    global _engine, _async_session_factory

    db_url = str(settings.DATABASE_URL)
    engine_kwargs: dict[str, Any] = {
        "echo": settings.DEBUG,
        "future": True,
    }

    if "sqlite" not in db_url:
        engine_kwargs.update(
            {
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "pool_pre_ping": True,
            }
        )

    _engine = create_async_engine(db_url, **engine_kwargs)

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    logger.debug("Async DB engine created: %s", db_url)


async def close_db() -> None:
    """Dispose the engine and release all pooled connections."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.debug("Async DB engine disposed")


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory; raises if init_db was not called."""
    if _async_session_factory is None:
        raise RuntimeError("Database not initialised.  Call init_db() first.")
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency-injectable async session generator.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)): ...
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
