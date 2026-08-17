"""
api/v1/endpoints/health.py

Health-check endpoint.
Returns the service status and live connectivity state of PostgreSQL and Redis.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.dependencies.cache import get_cache
from app.dependencies.db import get_db
from app.schemas.common import HealthResponse
from app.utils.cache import CacheClient

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service health and dependency status.",
)
async def health_check(
    db: AsyncSession = Depends(get_db),
    cache: CacheClient = Depends(get_cache),
) -> HealthResponse:
    """
    Liveness + readiness probe.

    - `db`    – executes `SELECT 1` against PostgreSQL.
    - `redis` – issues a PING to Redis.
    """
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        await cache._client.ping()
    except Exception:
        redis_status = "error"

    return HealthResponse(
        status="ok" if db_status == "ok" and redis_status == "ok" else "degraded",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        db=db_status,
        redis=redis_status,
    )
