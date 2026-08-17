"""
tests/conftest.py

Shared pytest fixtures for unit and integration tests.
Supports in-memory async SQLite engine with PostgreSQL type compatibility,
transaction rollback isolation per test, and async HTTP test client.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.core.application import create_application
from app.db.base import Base
from app.dependencies.cache import get_cache
from app.dependencies.db import get_db
from app.utils.cache import CacheClient


# ── SQLite compatibility for PostgreSQL INET type ─────────────────────────────
@compiles(INET, "sqlite")
def compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeCacheClient(CacheClient):
    """In-memory cache client for isolated testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def _key(self, *parts: str) -> str:
        return ":".join(parts)

    async def get(self, *key_parts: str):
        return self._store.get(self._key(*key_parts))

    async def set(self, *key_parts: str, value: str, ttl: int = 0) -> None:
        self._store[self._key(*key_parts)] = value

    async def delete(self, *key_parts: str) -> None:
        self._store.pop(self._key(*key_parts), None)

    async def get_original_url(self, short_code: str):
        return self._store.get(f"url_shortener:short:{short_code}")

    async def set_short_url(self, short_code: str, original_url: str, ttl_seconds: int = 1800):
        self._store[f"url_shortener:short:{short_code}"] = original_url

    async def evict_short_code(self, short_code: str):
        self._store.pop(f"url_shortener:short:{short_code}", None)


@pytest.fixture
async def test_engine():
    """Create in-memory SQLite async engine and initialize tables per test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Isolated async DB session for tests."""
    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
def fake_cache():
    return FakeCacheClient()


@pytest.fixture
async def client(db_session: AsyncSession, fake_cache: FakeCacheClient) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with DB and fake cache overrides."""
    app = create_application()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_cache] = lambda: fake_cache

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
