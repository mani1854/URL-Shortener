"""
middleware/rate_limit.py

Tiered rate-limiting middleware backed by Redis.

Rules:
  - Anonymous users: 50 requests / hour (tracked by IP address)
  - Authenticated users: 500 requests / hour (tracked by User UUID from JWT)
  - Returns HTTP 429 Too Many Requests when quota is exceeded with standard
    X-RateLimit-* and Retry-After headers.
  - Excludes health check, documentation, and OpenAPI specification routes.
  - Fail-Open: Transient Redis connection failures allow requests through.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.security import decode_access_token
from app.utils.client_info import extract_client_ip

logger = logging.getLogger(__name__)

# Paths exempt from rate limits (health checks, monitoring, API documentation)
EXEMPT_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    f"{settings.API_V1_PREFIX}/health",
    f"{settings.API_V1_PREFIX}/openapi.json",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed sliding window rate limiter with tier-based quota allocation.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Skip rate-limiting on exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # 2. Determine rate-limit tier and identifier (User ID or IP)
        tier, identifier, limit = self._identify_client(request)
        key = f"url_shortener:rate_limit:{tier}:{identifier}"
        window = settings.RATE_LIMIT_WINDOW_SECONDS

        # 3. Check and increment Redis rate limit counter
        is_limited, current_count, ttl = await self._check_rate_limit(key, window)

        # 4. If quota exceeded, return HTTP 429 Too Many Requests
        if is_limited and current_count > limit:
            retry_after = max(1, ttl)
            logger.warning(
                "Rate limit exceeded: tier=%s, id=%s, count=%d, limit=%d",
                tier, identifier, current_count, limit
            )
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "errors": [
                        {
                            "message": f"Rate limit exceeded ({limit} requests/hour). Please try again in {retry_after} seconds."
                        }
                    ],
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        # 5. Execute downstream request handler
        response: Response = await call_next(request)

        # 6. Inject standard rate limit headers into successful response
        remaining = max(0, limit - current_count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if ttl > 0:
            response.headers["X-RateLimit-Reset"] = str(ttl)

        return response

    @staticmethod
    def _identify_client(request: Request) -> tuple[str, str, int]:
        """
        Identify request tier (auth vs anon), tracking key identifier, and quota limit.

        Returns:
            (tier, identifier, limit)
        """
        # Check for Authorization: Bearer <token>
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            try:
                payload = decode_access_token(token)
                user_id = payload.get("sub")
                if user_id:
                    return ("user", str(user_id), settings.RATE_LIMIT_AUTH_REQUESTS)
            except Exception:
                # Invalid or expired token falls back to IP-based rate limiting
                pass

        # Anonymous fallback using client IP
        client_ip = extract_client_ip(request) or "unknown"
        return ("ip", client_ip, settings.RATE_LIMIT_ANON_REQUESTS)

    @staticmethod
    async def _check_rate_limit(key: str, window_seconds: int) -> tuple[bool, int, int]:
        """
        Atomically increment counter in Redis with TTL expiration.

        Returns:
            (is_limited, current_count, ttl_seconds)
        """
        try:
            from app.utils.cache import get_redis
            redis_client = get_redis()

            # Atomic pipeline: INCR and TTL
            pipe = redis_client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()

            current_count = int(results[0])
            ttl = int(results[1])

            # Set expiration on first hit or if key lacks TTL
            if current_count == 1 or ttl == -1:
                await redis_client.expire(key, window_seconds)
                ttl = window_seconds

            return (True, current_count, ttl)
        except RuntimeError:
            # Redis not initialized (e.g. minimal unit test runner) -> fail open
            return (False, 0, 0)
        except Exception as exc:
            # Fail-open: network or Redis outage allows traffic through with warning
            logger.warning("Rate limit check failed (failing open): %s", exc)
            return (False, 0, 0)
