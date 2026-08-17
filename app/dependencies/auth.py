"""
dependencies/auth.py

FastAPI dependency callables for authentication and authorisation.

Usage in route handlers:
    # Require any authenticated user:
    async def route(user: User = Depends(get_current_active_user)): ...

    # Require a superuser:
    async def admin_route(user: User = Depends(require_superuser)): ...

    # Optionally authenticated (returns None for anonymous requests):
    async def public_route(user: User | None = Depends(get_optional_user)): ...
"""

from __future__ import annotations

import logging

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
)
from app.core.security import decode_access_token
from app.dependencies.db import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id

logger = logging.getLogger(__name__)

# HTTPBearer extracts "Authorization: Bearer <token>" from the request header.
# auto_error=False means it returns None instead of raising 403 for missing tokens
# — we handle the error ourselves to return a consistent error shape.
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT and return the corresponding User row.

    Raises:
        InvalidTokenError (401): if the token is missing, malformed, expired,
            or belongs to a deleted user.
    """
    if credentials is None:
        raise InvalidTokenError(detail="Authorization header is missing.")

    payload = decode_access_token(credentials.credentials)  # raises on bad token
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise InvalidTokenError(detail="Token payload is missing 'sub' claim.")

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise InvalidTokenError(detail="User associated with this token no longer exists.")

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Return the authenticated user only if the account is active.

    Raises:
        InactiveUserError (403): if ``user.is_active`` is False.
    """
    if not user.is_active:
        raise InactiveUserError()
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Return the authenticated user or **None** for unauthenticated requests.

    This enables routes that behave differently for authenticated vs anonymous
    users (e.g. URL shortening — anonymous links vs. owned links).
    """
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if not user_id:
            return None
        return await get_user_by_id(db, user_id)
    except Exception:
        return None


async def require_superuser(
    user: User = Depends(get_current_active_user),
) -> User:
    """
    Return the authenticated user only if they are a superuser.

    Raises:
        PermissionDeniedError (403): if ``user.is_superuser`` is False.
    """
    if not user.is_superuser:
        raise PermissionDeniedError(detail="Superuser access required.")
    return user
