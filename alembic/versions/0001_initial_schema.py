"""Initial schema – users, urls, click_analytics

Revision ID: 0001_initial_schema
Revises: (none)
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── PostgreSQL extensions ──────────────────────────────────────────────────
    # uuid-ossp: gen_random_uuid() fallback for older PG versions
    # pg_trgm:   future trigram/similarity search on original_url
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ──────────────────────────────────────────────────────────────────────────
    # Table: users
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        # ── Surrogate PK ──────────────────────────────────────────────────────
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Surrogate primary key.",
        ),
        # ── Identity ──────────────────────────────────────────────────────────
        sa.Column(
            "email",
            sa.String(320),
            nullable=False,
            comment="User e-mail address (unique, case-insensitive login).",
        ),
        sa.Column(
            "hashed_password",
            sa.String(128),
            nullable=False,
            comment="bcrypt-hashed password.  Never store plaintext.",
        ),
        # ── Status flags ──────────────────────────────────────────────────────
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Soft-disable without deleting the account.",
        ),
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Grants administrative privileges.",
        ),
        # ── Timestamps ────────────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row creation timestamp (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row last-update timestamp (UTC).",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    # Indexes on users
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Table: urls
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        "urls",
        # ── Surrogate PK ──────────────────────────────────────────────────────
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Surrogate primary key.",
        ),
        # ── Core ──────────────────────────────────────────────────────────────
        sa.Column(
            "original_url",
            sa.Text(),
            nullable=False,
            comment="The original long URL that was shortened.",
        ),
        sa.Column(
            "short_code",
            sa.String(50),
            nullable=False,
            comment="URL-safe short code (random or custom alias).",
        ),
        # ── Ownership ─────────────────────────────────────────────────────────
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_urls_user_id"),
            nullable=True,
            comment="Owning user; NULL for anonymous/public links.",
        ),
        # ── Optional metadata ─────────────────────────────────────────────────
        sa.Column(
            "title",
            sa.String(255),
            nullable=True,
            comment="Optional human-readable title.",
        ),
        # ── Expiry / status ───────────────────────────────────────────────────
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Optional UTC expiry.  NULL means the link never expires.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Soft-disable without hard-deleting the record.",
        ),
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True when the short_code was supplied by the user.",
        ),
        # ── Analytics counter (denormalised) ──────────────────────────────────
        sa.Column(
            "click_count",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Denormalised click counter updated on each redirect.",
        ),
        # ── Timestamps ────────────────────────────────────────────────────────
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row creation timestamp (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row last-update timestamp (UTC).",
        ),
        sa.UniqueConstraint("short_code", name="uq_urls_short_code"),
    )
    # Indexes on urls
    op.create_index("ix_urls_short_code", "urls", ["short_code"], unique=True)
    op.create_index("ix_urls_user_id", "urls", ["user_id"])
    op.create_index("ix_urls_user_id_is_active", "urls", ["user_id", "is_active"])
    op.create_index("ix_urls_short_code_is_active", "urls", ["short_code", "is_active"])
    op.create_index("ix_urls_expires_at", "urls", ["expires_at"])

    # ──────────────────────────────────────────────────────────────────────────
    # Table: click_analytics
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        "click_analytics",
        # ── Surrogate PK ──────────────────────────────────────────────────────
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Surrogate primary key.",
        ),
        # ── Foreign key ───────────────────────────────────────────────────────
        sa.Column(
            "url_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "urls.id",
                ondelete="CASCADE",
                name="fk_click_analytics_url_id",
            ),
            nullable=False,
            comment="The short URL that was clicked.",
        ),
        # ── Request context ───────────────────────────────────────────────────
        sa.Column(
            "ip_address",
            postgresql.INET(),
            nullable=True,
            comment="Client IP address (IPv4 or IPv6).  NULL in privacy mode.",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Raw User-Agent header string.",
        ),
        # ── Geo enrichment ────────────────────────────────────────────────────
        sa.Column(
            "country",
            sa.String(2),
            nullable=True,
            comment="ISO 3166-1 alpha-2 country code from GeoIP lookup.",
        ),
        sa.Column(
            "city",
            sa.String(100),
            nullable=True,
            comment="City name from GeoIP lookup (best-effort).",
        ),
        # ── Device / browser ──────────────────────────────────────────────────
        sa.Column(
            "device_type",
            sa.String(20),
            nullable=True,
            comment="Coarse device category: desktop|mobile|tablet|bot|unknown.",
        ),
        sa.Column(
            "browser",
            sa.String(50),
            nullable=True,
            comment="Browser family parsed from User-Agent.",
        ),
        sa.Column(
            "os",
            sa.String(50),
            nullable=True,
            comment="Operating system parsed from User-Agent.",
        ),
        # ── Referrer ──────────────────────────────────────────────────────────
        sa.Column(
            "referer",
            sa.Text(),
            nullable=True,
            comment="HTTP Referer header (origin page of the click).",
        ),
        # ── Timestamps ────────────────────────────────────────────────────────
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="UTC timestamp when the click occurred.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row creation timestamp (UTC).",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Row last-update timestamp (UTC).",
        ),
    )
    # Indexes on click_analytics
    op.create_index("ix_click_analytics_url_id", "click_analytics", ["url_id"])
    op.create_index(
        "ix_click_analytics_url_id_timestamp",
        "click_analytics",
        ["url_id", "timestamp"],
    )
    op.create_index(
        "ix_click_analytics_url_id_country",
        "click_analytics",
        ["url_id", "country"],
    )
    op.create_index(
        "ix_click_analytics_ip_address",
        "click_analytics",
        ["ip_address"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_click_analytics_ip_address",        table_name="click_analytics")
    op.drop_index("ix_click_analytics_url_id_country",    table_name="click_analytics")
    op.drop_index("ix_click_analytics_url_id_timestamp",  table_name="click_analytics")
    op.drop_index("ix_click_analytics_url_id",            table_name="click_analytics")
    op.drop_table("click_analytics")

    op.drop_index("ix_urls_expires_at",          table_name="urls")
    op.drop_index("ix_urls_short_code_is_active", table_name="urls")
    op.drop_index("ix_urls_user_id_is_active",   table_name="urls")
    op.drop_index("ix_urls_user_id",             table_name="urls")
    op.drop_index("ix_urls_short_code",          table_name="urls")
    op.drop_table("urls")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
