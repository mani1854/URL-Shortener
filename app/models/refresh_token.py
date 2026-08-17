"""
models/refresh_token.py

ORM model for persisted refresh tokens.

Design decisions:
  - Each row represents one active session; a user can have multiple sessions
    (e.g. phone + laptop) up to MAX_SESSIONS_PER_USER (enforced in service).
  - Tokens are hashed before storage so that a DB breach does not expose
    bearer tokens (similar to how passwords are never stored in plain text).
  - ON DELETE CASCADE: deleting a user wipes all their sessions automatically.
  - is_revoked flag enables explicit logout without immediate deletion,
    preserving an audit trail.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RefreshToken(Base):
    """Represents one active refresh-token session."""

    __tablename__ = "refresh_tokens"

    # ── Primary Key ────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate primary key.",
    )

    # ── Foreign Key ────────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_refresh_tokens_user_id"),
        nullable=False,
        index=True,
        comment="The user this session belongs to.",
    )

    # ── Token ──────────────────────────────────────────────────────────────────
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        comment="SHA-256 hex digest of the raw refresh token string.",
    )

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="UTC timestamp after which the token is no longer valid.",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
        comment="True after explicit logout or token rotation.",
    )

    # ── Device hint (optional, aids UX for session management) ────────────────
    user_agent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Truncated User-Agent of the client that created this session.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped[User] = relationship(  # noqa: F821
        "User",
        back_populates="refresh_tokens",
        lazy="select",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # Used when listing active sessions for a user
        Index("ix_refresh_tokens_user_id_is_revoked", "user_id", "is_revoked"),
        # Fast expiry sweep jobs
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.is_revoked}>"
