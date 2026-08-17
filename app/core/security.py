"""
core/security.py

Cryptographic helpers:
  - Password hashing and verification using bcrypt (via passlib).
  - JWT access-token creation and decoding (via python-jose).
  - Refresh-token generation (cryptographically secure random string).

Nothing in this module touches the database or HTTP layer — it is a
pure utility that services and dependencies import from.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt is the only scheme; deprecated="auto" auto-migrates old hashes.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash of *plain_password*."""
    return _pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    return _pwd_context.verify(plain_password, hashed_password)


# ── JWT access tokens ─────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject:      The ``sub`` claim – typically the user's UUID as a string.
        extra_claims: Any additional claims to embed (e.g. ``{"role": "admin"}``).
        expires_delta: Override the default TTL from settings.

    Returns:
        A signed JWT string.
    """
    now = datetime.now(UTC)
    expire = now + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Raises:
        TokenExpiredError:  if the token's ``exp`` claim is in the past.
        InvalidTokenError:  if the token is malformed, has a wrong signature,
                            or is not of ``type == "access"``.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError() from None
    except JWTError:
        raise InvalidTokenError() from None

    if payload.get("type") != "access":
        raise InvalidTokenError(detail="Token type is not 'access'.")

    return payload


# ── Refresh tokens ────────────────────────────────────────────────────────────

def generate_refresh_token() -> str:
    """
    Generate a cryptographically secure refresh token string.

    Uses ``secrets.token_urlsafe`` which produces a URL-safe, base64-encoded
    random string suitable for storing in the database and sending to clients.

    Returns:
        A 64-character (48-byte) URL-safe random string.
    """
    return secrets.token_urlsafe(48)


def refresh_token_expiry() -> datetime:
    """Return the UTC datetime when a new refresh token should expire."""
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
