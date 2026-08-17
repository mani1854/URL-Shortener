"""
core/events.py

Application lifespan context manager (replaces deprecated on_event hooks).
Handles startup and shutdown of long-lived resources:
  - Database connection pool (SQLAlchemy async engine)
  - Redis connection pool
  - Structured logging initialisation
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import close_db, init_db
from app.utils.cache import close_redis, init_redis

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Everything before `yield` runs on startup;
    everything after `yield` runs on shutdown.
    """
    # ── Startup ────────────────────────────────────────────────────────────────
    configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
    logger.info("Starting up %s (env=%s)", settings.APP_NAME, settings.APP_ENV)

    await init_db()
    logger.info("Database pool initialised")

    if "sqlite" in str(settings.DATABASE_URL):
        from app.db.base import Base
        from app.db.session import _engine
        if _engine is not None:
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Local database schema verified")

    await init_redis()
    logger.info("Redis pool initialised")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down %s …", settings.APP_NAME)
    await close_redis()
    await close_db()
    logger.info("Shutdown complete")
