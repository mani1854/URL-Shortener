"""Add refresh_tokens table

Revision ID: 0002_add_refresh_tokens
Revises: 0001_initial_schema
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────
revision: str = "0002_add_refresh_tokens"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────────────
    # Table: refresh_tokens
    #
    # Stores one row per active user session.
    # The raw token string is NEVER stored; only its SHA-256 hex digest is
    # persisted so a DB breach cannot be used to impersonate users.
    # ──────────────────────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Surrogate primary key.",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="fk_refresh_tokens_user_id",
            ),
            nullable=False,
            comment="The user this session belongs to.",
        ),
        sa.Column(
            "token_hash",
            sa.String(128),
            nullable=False,
            comment="SHA-256 hex digest of the raw refresh token string.",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="UTC timestamp after which the token is no longer valid.",
        ),
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True after explicit logout or token rotation.",
        ),
        sa.Column(
            "user_agent",
            sa.String(255),
            nullable=True,
            comment="Truncated User-Agent of the client that created this session.",
        ),
        # ── Timestamps (inherited from Base) ───────────────────────────────────
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
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )

    # ── Indexes on refresh_tokens ──────────────────────────────────────────────
    op.create_index(
        "ix_refresh_tokens_user_id",
        "refresh_tokens",
        ["user_id"],
    )
    op.create_index(
        "ix_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_refresh_tokens_user_id_is_revoked",
        "refresh_tokens",
        ["user_id", "is_revoked"],
    )
    op.create_index(
        "ix_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at",        table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id_is_revoked", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash",        table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id",           table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
