"""
core/application.py

FastAPI Application factory.
Configures middleware, OpenAPI metadata, Swagger UI / ReDoc parameters,
routes, exception handlers, and lifespan event hooks.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.events import lifespan
from app.core.exception_handlers import register_exception_handlers
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

logger = logging.getLogger(__name__)

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "System liveness, readiness, and PostgreSQL/Redis dependency health probes.",
    },
    {
        "name": "Authentication",
        "description": "User registration, JWT login, token refresh rotation, and profile queries.",
    },
    {
        "name": "URLs",
        "description": "URL shortening, Base62 code generation, custom aliases, metadata, and 302 redirects.",
    },
    {
        "name": "Analytics",
        "description": "Time-series click metrics, GeoIP country breakdown, browser, and device platform distributions.",
    },
    {
        "name": "Dashboard",
        "description": "Authenticated user link management: paginated URL listing, expiry updates, and soft deletions.",
    },
]


def create_application() -> FastAPI:
    """
    FastAPI application factory.

    Returns:
        A fully configured FastAPI instance ready for development or production deployment.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "A high-performance URL shortening and analytics microservice built with "
            "FastAPI, SQLAlchemy, Redis, and PostgreSQL."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
            "defaultModelsExpandDepth": 2,
            "docExpansion": "list",
        },
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # ── Custom OpenAPI schema generation ──────────────────────────────────────
    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return application.openapi_schema
        openapi_schema = get_openapi(
            title=settings.APP_NAME,
            version=settings.APP_VERSION,
            description=(
                "### Production-Ready URL Shortener API\n\n"
                "A scalable link management microservice with:\n"
                "- **Base62 & Custom Slugs**: Sub-millisecond generation with collision avoidance.\n"
                "- **Redis Multi-tier Caching**: 30-minute Cache-Aside with write-invalidation.\n"
                "- **Async Analytics**: Non-blocking GeoIP, browser, OS, and device telemetry via BackgroundTasks.\n"
                "- **Tiered Rate Limiting**: 50 req/hr (Anonymous) / 500 req/hr (Authenticated).\n"
                "- **JWT Security**: Access tokens and rotated Refresh tokens.\n"
            ),
            routes=application.routes,
            tags=OPENAPI_TAGS,
        )
        application.openapi_schema = openapi_schema
        return application.openapi_schema

    application.openapi = custom_openapi  # type: ignore[method-assign]

    # ── Middleware (order matters – outermost registered first) ────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(RateLimitMiddleware)

    # ── Static Files & Frontend ────────────────────────────────────────────────
    from pathlib import Path

    from fastapi.responses import FileResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @application.get("/", include_in_schema=False)
        async def serve_index():
            return FileResponse(static_dir / "index.html")

    # ── Routers ────────────────────────────────────────────────────────────────
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Top-level direct redirect route: GET /{short_code}
    from app.api.v1.endpoints.urls import redirect_to_original

    application.add_api_route(
        "/{short_code}",
        redirect_to_original,
        methods=["GET"],
        response_class=RedirectResponse,
        status_code=302,
        summary="Top-level redirect",
        include_in_schema=False,
    )

    # ── Exception handlers ─────────────────────────────────────────────────────
    register_exception_handlers(application)

    logger.info("Application factory complete – %s v%s", settings.APP_NAME, settings.APP_VERSION)
    return application
