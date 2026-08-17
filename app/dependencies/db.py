"""
dependencies/db.py

FastAPI dependency for injecting an async SQLAlchemy session.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db as _get_db


async def get_db(
    session: AsyncSession = Depends(_get_db),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Re-export of the session generator as a typed FastAPI dependency.

    Usage in a route:
        async def my_route(db: AsyncSession = Depends(get_db)): ...
    """
    yield session
