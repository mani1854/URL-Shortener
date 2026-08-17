"""
models/click_analytics.py

ORM model for per-click analytics records.
Each redirect event writes one row to this table so that click-level
detail can be queried (geo, device, time-series) without touching the
denormalised counter on the URL row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ClickAnalytics(Base):
    """Represents a single click/redirect event for a short URL."""

    __tablename__ = "click_analytics"

    # ── Primary Key ────────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Surrogate primary key.",
    )

    # ── Foreign Key ────────────────────────────────────────────────────────────
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The short URL that was clicked.",
    )

    # ── Request Context ────────────────────────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(
        INET,                 # PostgreSQL native IP type (supports IPv4 & IPv6)
        nullable=True,
        comment="Client IP address.  NULL if not captured (privacy mode).",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw User-Agent header string.",
    )

    # ── Geo enrichment (populated asynchronously via a GeoIP lookup) ───────────
    country: Mapped[str | None] = mapped_column(
        String(2),            # ISO 3166-1 alpha-2 country code
        nullable=True,
        comment="Two-letter ISO country code resolved from ip_address.",
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="City name resolved from ip_address (best-effort).",
    )

    # ── Device / Browser (parsed from user_agent) ─────────────────────────────
    device_type: Mapped[str | None] = mapped_column(
        String(20),           # "desktop" | "mobile" | "tablet" | "bot" | "unknown"
        nullable=True,
        comment="Coarse device category parsed from User-Agent.",
    )
    browser: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Browser family parsed from User-Agent.",
    )
    os: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Operating system parsed from User-Agent.",
    )

    # ── Referrer ───────────────────────────────────────────────────────────────
    referer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="HTTP Referer header (origin page).",
    )

    # ── Timestamp ─────────────────────────────────────────────────────────────
    # Override Base.created_at default for clarity; this IS the click timestamp.
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="UTC timestamp when the click occurred.",
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    url: Mapped[URL] = relationship(  # noqa: F821
        "URL",
        back_populates="clicks",
        lazy="select",
    )

    # ── Indexes ────────────────────────────────────────────────────────────────
    __table_args__ = (
        # Time-series queries: "clicks for URL X in the last 30 days"
        Index("ix_click_analytics_url_id_timestamp", "url_id", "timestamp"),
        # Geo aggregations: "top countries for URL X"
        Index("ix_click_analytics_url_id_country", "url_id", "country"),
        # De-duplication / abuse detection
        Index("ix_click_analytics_ip_address", "ip_address"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ClickAnalytics id={self.id} url_id={self.url_id} "
            f"timestamp={self.timestamp!r}>"
        )
