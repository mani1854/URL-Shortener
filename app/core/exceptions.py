"""
core/exceptions.py

Domain-level exceptions.  All custom exceptions raised inside services and
repositories inherit from AppException so that a single exception handler in
the API layer can translate them to appropriate HTTP responses.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application-level errors."""

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None, **context: Any) -> None:
        self.detail = detail or self.__class__.detail
        self.context = context
        super().__init__(self.detail)


# ── 400 Bad Request ────────────────────────────────────────────────────────────
class InvalidURLError(AppException):
    status_code = 400
    detail = "The provided URL is not valid."


class AliasAlreadyExistsError(AppException):
    status_code = 400
    detail = "The requested custom alias is already taken."


# ── 401 Unauthorised ──────────────────────────────────────────────────────────
class InvalidCredentialsError(AppException):
    status_code = 401
    detail = "Incorrect email or password."


class InvalidTokenError(AppException):
    status_code = 401
    detail = "Token is invalid or has been revoked."


class TokenExpiredError(AppException):
    status_code = 401
    detail = "Token has expired."


# ── 409 Conflict ──────────────────────────────────────────────────────────────
class EmailAlreadyExistsError(AppException):
    status_code = 409
    detail = "An account with this email address already exists."


# ── 404 Not Found ──────────────────────────────────────────────────────────────
class ShortURLNotFoundError(AppException):
    status_code = 404
    detail = "Short URL not found."


# ── 410 Gone ──────────────────────────────────────────────────────────────────
class URLExpiredError(AppException):
    status_code = 410
    detail = "This short URL has expired."


# ── 429 Too Many Requests ─────────────────────────────────────────────────────
class RateLimitExceededError(AppException):
    status_code = 429
    detail = "Rate limit exceeded. Please slow down."


# ── 403 Forbidden ─────────────────────────────────────────────────────────────
class PermissionDeniedError(AppException):
    status_code = 403
    detail = "You do not have permission to perform this action."


class InactiveUserError(AppException):
    status_code = 403
    detail = "This account has been deactivated."
