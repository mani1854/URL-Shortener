"""
db/base.py

SQLAlchemy declarative base.
All ORM models must import and extend `Base` from this module so that
Alembic's `env.py` can discover them via `Base.metadata`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


@compiles(INET, "sqlite")
def compile_inet_sqlite(element: Any, compiler: Any, **kw: Any) -> str:
    return "VARCHAR(45)"


class Base(DeclarativeBase):
    """
    Project-wide declarative base with automatic timestamp columns.

    All models that inherit from this class will automatically receive:
        - created_at: timestamp of first insert (UTC)
        - updated_at: timestamp of last update (UTC)
    """

    # ── Shared audit columns ───────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        cols = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in self.__table__.columns
        )
        return f"<{self.__class__.__name__}({cols})>"
