"""
core/exception_handlers.py

FastAPI exception handlers.

Registered in app/core/application.py so that every AppException subclass
is translated to a structured JSON error response instead of an unhandled
500.  Validation errors from Pydantic are also normalised into the same
ErrorResponse shape.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

from app.core.exceptions import AppException
from app.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all custom exception handlers to *app*."""

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> ORJSONResponse:
        """Translate any AppException subclass → structured JSON error."""
        logger.warning(
            "AppException raised: %s – %s",
            exc.__class__.__name__,
            exc.detail,
        )
        return ORJSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                errors=[ErrorDetail(message=exc.detail)]
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        """Translate Pydantic validation errors → structured JSON error list."""
        errors = [
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"] if loc != "body"),
                message=error["msg"],
                code=error["type"],
            )
            for error in exc.errors()
        ]
        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(errors=errors).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        """Catch-all for unexpected errors — never expose internals."""
        logger.exception("Unhandled exception: %s", exc)
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                errors=[ErrorDetail(message="An unexpected internal error occurred.")]
            ).model_dump(),
        )
