"""
models/url.py

ORM model for a shortened URL record.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class URL(Base):
    """Represents a shortened URL entry."""

    __tablename__ = "urls"

    # ── Primary Key ────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate primary key.",
    )

    # ── Core Fields ────────────────────────────────────────────────────────────
    original_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The original long URL that was shortened.",
    )
    short_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="URL-safe short code (random or custom alias).",
    )

    # ── Ownership ──────────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Owning user; NULL for anonymous/public links.",
    )

    # ── Optional Metadata ──────────────────────────────────────────────────────
    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Optional human-readable title scraped or supplied by user.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description.",
    )

    # ── Expiry / Status ────────────────────────────────────────────────────────
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Optional UTC expiry.  NULL means the link never expires.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Soft-disable without hard-deleting the record.",
    )
    is_custom: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True when the short_code was supplied by the user.",
    )

    # ── Analytics Counter (denormalised for fast reads) ────────────────────────
    click_count: Mapped[int] = mapped_column(
        BigInteger,           # supports billions of clicks
        default=0,
        nullable=False,
        server_default="0",
        comment="Denormalised click counter updated on each redirect.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    owner: Mapped[User] = relationship(  # noqa: F821
        "User",
        back_populates="urls",
        lazy="select",
    )
    clicks: Mapped[list[ClickAnalytics]] = relationship(  # noqa: F821
        "ClickAnalytics",
        back_populates="url",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    # ── Composite indexes ──────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_urls_user_id_is_active", "user_id", "is_active"),
        Index("ix_urls_short_code_is_active", "short_code", "is_active"),
        Index("ix_urls_expires_at", "expires_at"),       # for TTL sweep jobs
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<URL id={self.id} short_code={self.short_code!r}>"
