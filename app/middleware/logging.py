"""
middleware/logging.py

Request/response logging middleware.
Adds a unique `X-Request-ID` header to every response and emits a
structured log line with method, path, status, and latency.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

try:
    import structlog
    HAS_STRUCTLOG = True
    logger = structlog.get_logger(__name__)
except ImportError:
    HAS_STRUCTLOG = False
    logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that:
      1. Assigns a unique request ID to each request.
      2. Binds the request ID to the logging context for log correlation.
      3. Logs method, path, status code, and latency on completion.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())

        if HAS_STRUCTLOG:
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )

        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("Unhandled exception during request [%s]", request_id)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            status_code = response.status_code if response is not None else 500
            if HAS_STRUCTLOG:
                logger.info(
                    "request_complete",
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                )
            else:
                logger.info(
                    "[%s] %s %s -> %s (%.2fms)",
                    request_id,
                    request.method,
                    request.url.path,
                    status_code,
                    duration_ms,
                )
