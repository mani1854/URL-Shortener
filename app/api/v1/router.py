"""
api/v1/router.py

Root API router for v1.
All endpoint routers are registered here and included in the main app
via app/core/application.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, dashboard, health, urls
from app.schemas.common import APIResponse
from app.schemas.url import URLResponse

api_router = APIRouter()

# ── Route modules ──────────────────────────────────────────────────────────────
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router)
api_router.include_router(urls.router, prefix="/urls", tags=["URLs"])
api_router.include_router(analytics.router)
api_router.include_router(dashboard.router)

# Top-level /shorten convenience route
api_router.add_api_route(
    "/shorten",
    urls.create_short_url,
    methods=["POST"],
    response_model=APIResponse[URLResponse],
    status_code=201,
    summary="Shorten a URL",
    description="Direct convenience endpoint for URL shortening.",
    tags=["URLs"],
)
