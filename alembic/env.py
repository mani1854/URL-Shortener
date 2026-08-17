"""
alembic/env.py

Alembic environment configuration for async SQLAlchemy.
Reads DATABASE_URL from the application settings (loaded from .env)
and uses the sync wrapper `run_sync` to execute migrations against
an async engine.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# ── Load project settings & models ────────────────────────────────────────────
# This import triggers all model registrations against Base.metadata.
from app.core.config import settings
from app.db import Base  # noqa: F401 – triggers model registration

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy metadata target for --autogenerate
target_metadata = Base.metadata


# ── Migration runners ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (no DB connection required).
    Useful for generating SQL scripts to review before applying.
    """
    context.configure(
        url=str(settings.DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (connects to the DB and applies changes).
    Uses an async engine but wraps migrations in a sync context.
    """
    connectable = create_async_engine(
        str(settings.DATABASE_URL),
        poolclass=pool.NullPool,  # avoid pooling during migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
