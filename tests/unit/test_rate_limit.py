"""
tests/unit/test_rate_limit.py

Unit tests for RateLimitMiddleware:
  - Anonymous IP tier (50 requests/hour)
  - Authenticated User tier (500 requests/hour from JWT)
  - HTTP 429 response formatting with Retry-After and X-RateLimit headers
  - Exempt path bypass (/health, /docs)
  - Fail-open resilience when Redis is unreachable
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.core.security import create_access_token
from app.middleware.rate_limit import RateLimitMiddleware


@pytest.fixture
def middleware():
    app = MagicMock()
    return RateLimitMiddleware(app)


# ── Client Identification Unit Tests ──────────────────────────────────────────

class TestClientIdentification:
    def test_identify_anonymous_client(self, middleware):
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"198.51.100.25"),
            ],
        }
        req = Request(scope)
        tier, identifier, limit = middleware._identify_client(req)

        assert tier == "ip"
        assert identifier == "198.51.100.25"
        assert limit == 50

    def test_identify_authenticated_client(self, middleware):
        user_uuid = str(uuid.uuid4())
        token = create_access_token(subject=user_uuid)

        scope = {
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {token}".encode()),
            ],
        }
        req = Request(scope)
        tier, identifier, limit = middleware._identify_client(req)

        assert tier == "user"
        assert identifier == user_uuid
        assert limit == 500

    def test_identify_invalid_token_falls_back_to_ip(self, middleware):
        scope = {
            "type": "http",
            "headers": [
                (b"authorization", b"Bearer invalid-garbage-token"),
                (b"x-real-ip", b"203.0.113.88"),
            ],
        }
        req = Request(scope)
        tier, identifier, limit = middleware._identify_client(req)

        assert tier == "ip"
        assert identifier == "203.0.113.88"
        assert limit == 50


# ── Rate Limit Middleware Dispatch Tests ──────────────────────────────────────

@pytest.mark.anyio
async def test_middleware_allows_under_limit(middleware):
    """Requests under quota proceed and receive X-RateLimit-* headers."""
    scope = {
        "type": "http",
        "path": "/api/v1/urls",
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
    }
    req = Request(scope)

    async def dummy_next(request):
        return PlainTextResponse("OK")

    # Mock Redis pipeline: returns (count=5, ttl=3500)
    with patch.object(
        RateLimitMiddleware, "_check_rate_limit", AsyncMock(return_value=(True, 5, 3500))
    ):
        response = await middleware.dispatch(req, dummy_next)

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "50"
        assert response.headers["X-RateLimit-Remaining"] == "45"
        assert response.headers["X-RateLimit-Reset"] == "3500"


@pytest.mark.anyio
async def test_middleware_blocks_anonymous_over_50(middleware):
    """Anonymous requests exceeding 50 return HTTP 429 with Retry-After."""
    scope = {
        "type": "http",
        "path": "/api/v1/urls",
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
    }
    req = Request(scope)

    async def dummy_next(request):
        return PlainTextResponse("OK")

    # Mock Redis pipeline returning count=51 (exceeded)
    with patch.object(
        RateLimitMiddleware, "_check_rate_limit", AsyncMock(return_value=(True, 51, 1800))
    ):
        response = await middleware.dispatch(req, dummy_next)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1800"
        assert response.headers["X-RateLimit-Limit"] == "50"
        assert response.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.anyio
async def test_middleware_authenticated_allows_up_to_500(middleware):
    """Authenticated user with count=499 is allowed with remaining=1."""
    user_uuid = str(uuid.uuid4())
    token = create_access_token(subject=user_uuid)
    scope = {
        "type": "http",
        "path": "/api/v1/urls",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    }
    req = Request(scope)

    async def dummy_next(request):
        return PlainTextResponse("OK")

    with patch.object(
        RateLimitMiddleware, "_check_rate_limit", AsyncMock(return_value=(True, 499, 3600))
    ):
        response = await middleware.dispatch(req, dummy_next)

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "500"
        assert response.headers["X-RateLimit-Remaining"] == "1"


@pytest.mark.anyio
async def test_middleware_exempt_paths_bypass(middleware):
    """Health check routes are not subject to rate limiting."""
    scope = {
        "type": "http",
        "path": "/health",
        "headers": [],
    }
    req = Request(scope)

    called = False

    async def dummy_next(request):
        nonlocal called
        called = True
        return PlainTextResponse("HEALTHY")

    with patch.object(RateLimitMiddleware, "_check_rate_limit") as mock_check:
        response = await middleware.dispatch(req, dummy_next)

        assert response.status_code == 200
        assert called is True
        mock_check.assert_not_called()


@pytest.mark.anyio
async def test_middleware_fail_open_on_redis_error(middleware):
    """If Redis fails, request is allowed through with 200 OK (fail-open)."""
    scope = {
        "type": "http",
        "path": "/api/v1/urls",
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
    }
    req = Request(scope)

    async def dummy_next(request):
        return PlainTextResponse("OK")

    # When Redis check returns (False, 0, 0)
    with patch.object(
        RateLimitMiddleware, "_check_rate_limit", AsyncMock(return_value=(False, 0, 0))
    ):
        response = await middleware.dispatch(req, dummy_next)
        assert response.status_code == 200
