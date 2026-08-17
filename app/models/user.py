"""
models/user.py

ORM model for an authenticated user account.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """Represents a registered user."""

    __tablename__ = "users"

    # ── Primary Key ────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate primary key.",
    )

    # ── Identity ───────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(320),          # RFC 5321 maximum email length
        nullable=False,
        unique=True,
        index=True,
        comment="User e-mail address (unique, case-insensitive login).",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(128),          # bcrypt output is always 60 chars; 128 gives headroom
        nullable=False,
        comment="bcrypt-hashed password.  Never store plaintext.",
    )

    # ── Status ─────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Soft-disable without deleting the account.",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Grants administrative privileges.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    urls: Mapped[list[URL]] = relationship(  # noqa: F821
        "URL",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(  # noqa: F821
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="select",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"
