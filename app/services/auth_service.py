"""
services/auth_service.py

Authentication business logic.

Responsibilities:
  - User registration (signup)
  - Credential verification (login)
  - JWT access-token issuance
  - Refresh-token lifecycle (create, validate, rotate, revoke)

All database I/O goes through SQLAlchemy's async session.
No HTTP concerns live here — that belongs to the endpoint layer.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    refresh_token_expiry,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, TokenResponse

logger = logging.getLogger(__name__)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of *raw_token* for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def _get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def _get_refresh_token_row(
    db: AsyncSession, token_hash: str
) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    return result.scalar_one_or_none()


def _build_token_response(
    user: User,
    raw_refresh_token: str,
) -> TokenResponse:
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Public service functions ───────────────────────────────────────────────────

async def signup(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> TokenResponse:
    """
    Register a new user and return a token pair.

    Steps:
      1. Normalise email to lowercase.
      2. Check for uniqueness → raise EmailAlreadyExistsError on collision.
      3. Hash the password with bcrypt.
      4. Persist the User row.
      5. Create and persist a RefreshToken row.
      6. Return TokenResponse (access + refresh tokens).

    Raises:
        EmailAlreadyExistsError: if the email is already registered.
    """
    email = email.lower().strip()

    existing = await _get_user_by_email(db, email)
    if existing:
        raise EmailAlreadyExistsError()

    user = User(
        email=email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    await db.flush()        # populate user.id before FK reference

    raw_token = generate_refresh_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=refresh_token_expiry(),
    )
    db.add(refresh_row)
    await db.flush()

    logger.info("New user registered: %s", email)
    return _build_token_response(user, raw_token)


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    user_agent: str | None = None,
) -> TokenResponse:
    """
    Authenticate an existing user and return a token pair.

    Steps:
      1. Look up user by email.
      2. Verify bcrypt hash — constant-time comparison.
      3. Check account is active.
      4. Persist a new RefreshToken row (multi-session support).
      5. Return TokenResponse.

    Raises:
        InvalidCredentialsError: on email not found OR wrong password (same
            message intentionally to prevent user enumeration).
        InactiveUserError: if the account has been deactivated.
    """
    email = email.lower().strip()
    user = await _get_user_by_email(db, email)

    # Use verify_password even if user is None to prevent timing attacks
    dummy_hash = "$2b$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    candidate_hash = user.hashed_password if user else dummy_hash

    if not verify_password(password, candidate_hash) or user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InactiveUserError()

    raw_token = generate_refresh_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=refresh_token_expiry(),
        user_agent=(user_agent or "")[:255],
    )
    db.add(refresh_row)
    await db.flush()

    logger.info("User logged in: %s", email)
    return _build_token_response(user, raw_token)


async def refresh_access_token(
    db: AsyncSession,
    *,
    raw_refresh_token: str,
) -> AccessTokenResponse:
    """
    Exchange a valid refresh token for a new access token.

    Implements *refresh-token rotation*:
      - The old refresh-token row is marked is_revoked=True.
      - A brand-new refresh token is created and returned.
    This means a stolen token can only be used once before it is rotated away.

    Raises:
        InvalidTokenError: if the token is not found, already revoked, or expired.
    """
    token_hash = _hash_token(raw_refresh_token)
    row = await _get_refresh_token_row(db, token_hash)

    if row is None or row.is_revoked:
        raise InvalidTokenError(detail="Refresh token not found or already revoked.")

    exp = row.expires_at if row.expires_at.tzinfo is not None else row.expires_at.replace(tzinfo=UTC)
    if exp < datetime.now(UTC):
        raise InvalidTokenError(detail="Refresh token has expired.")

    # Rotate: revoke old, issue new
    row.is_revoked = True
    db.add(row)

    # Load user for claims
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise InvalidTokenError(detail="Associated user account is inactive.")

    new_raw = generate_refresh_token()
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(new_raw),
        expires_at=refresh_token_expiry(),
        user_agent=row.user_agent,
    )
    db.add(new_row)
    await db.flush()

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "is_superuser": user.is_superuser},
    )
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def logout(
    db: AsyncSession,
    *,
    raw_refresh_token: str,
) -> None:
    """
    Revoke a refresh token (logout from the current session).

    Raises:
        InvalidTokenError: if the token is not found.
    """
    token_hash = _hash_token(raw_refresh_token)
    row = await _get_refresh_token_row(db, token_hash)

    if row is None:
        raise InvalidTokenError(detail="Refresh token not found.")

    row.is_revoked = True
    db.add(row)
    await db.flush()
    logger.info("Refresh token revoked for user_id=%s", row.user_id)


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Fetch a User row by UUID string (used by the JWT dependency)."""
    import uuid as _uuid
    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        return None
    return await db.get(User, uid)
