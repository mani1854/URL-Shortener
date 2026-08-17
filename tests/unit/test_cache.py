"""
tests/unit/test_cache.py

Unit tests for Redis Cache-Aside pattern, 30-minute TTL, and cache invalidation.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.url import URL
from app.schemas.url import URLUpdateRequest
from app.services.url_service import URLService
from app.utils.cache import CacheClient


@pytest.fixture
def mock_redis():
    """Mock Redis client instance."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.exists = AsyncMock(return_value=1)
    return redis_mock


@pytest.fixture
def cache_client(mock_redis):
    return CacheClient(mock_redis)


@pytest.fixture
def mock_db():
    return AsyncMock()


# ── CacheClient Unit Tests ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_cache_get_and_set(cache_client, mock_redis):
    mock_redis.get.return_value = "https://destination.com"

    result = await cache_client.get_original_url("test1234")
    assert result == "https://destination.com"
    mock_redis.get.assert_called_once_with("url_shortener:short:test1234")

    await cache_client.set_original_url("test1234", "https://destination.com")
    mock_redis.setex.assert_called_once_with(
        "url_shortener:short:test1234", settings.CACHE_TTL_SECONDS, "https://destination.com"
    )


@pytest.mark.anyio
async def test_cache_eviction(cache_client, mock_redis):
    await cache_client.evict_short_code("test1234")
    mock_redis.delete.assert_called_once_with("url_shortener:short:test1234")


@pytest.mark.anyio
async def test_cache_graceful_error_handling(mock_redis):
    mock_redis.get.side_effect = Exception("Redis connection lost")
    mock_redis.setex.side_effect = Exception("Redis read-only")
    mock_redis.delete.side_effect = Exception("Redis error")

    client = CacheClient(mock_redis)
    # None of these should raise uncaught exceptions
    assert await client.get_original_url("code") is None
    assert await client.set_original_url("code", "https://url.com") is False
    assert await client.evict_short_code("code") is False


# ── Cache-Aside Service Integration Tests ─────────────────────────────────────

@pytest.mark.anyio
async def test_cache_aside_hit_bypasses_db(mock_db, cache_client, mock_redis):
    """When short code is cached in Redis, DB is never queried."""
    mock_redis.get.return_value = "https://cached-url.com"
    svc = URLService(db=mock_db, cache=cache_client)
    svc.repo.get_by_short_code = AsyncMock()

    url = await svc.resolve_short_code("hit123")
    assert url == "https://cached-url.com"
    svc.repo.get_by_short_code.assert_not_called()


@pytest.mark.anyio
async def test_cache_aside_miss_queries_db_and_sets_cache(mock_db, cache_client, mock_redis):
    """When cache misses, DB is queried and Redis key is set with 30m TTL."""
    mock_redis.get.return_value = None
    svc = URLService(db=mock_db, cache=cache_client)

    db_record = URL(
        id=uuid.uuid4(),
        original_url="https://db-resolved.com",
        short_code="miss123",
        is_active=True,
        expires_at=None,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=db_record)

    url = await svc.resolve_short_code("miss123")
    assert url == "https://db-resolved.com"
    mock_redis.setex.assert_called_once_with(
        "url_shortener:short:miss123", 1800, "https://db-resolved.com"
    )


@pytest.mark.anyio
async def test_cache_invalidated_on_url_update(mock_db, cache_client, mock_redis):
    """Updating a URL record immediately evicts the cached entry."""
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()
    record = URL(
        id=uuid.uuid4(),
        original_url="https://old-url.com",
        short_code="update123",
        user_id=user_id,
        is_active=True,
        expires_at=None,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)
    svc.repo.update = AsyncMock(return_value=record)

    payload = URLUpdateRequest(url="https://new-url.com")
    await svc.update_url("update123", payload, owner_id=user_id)

    mock_redis.delete.assert_called_once_with("url_shortener:short:update123")


@pytest.mark.anyio
async def test_cache_invalidated_on_url_delete(mock_db, cache_client, mock_redis):
    """Deleting a URL record immediately evicts the cached entry."""
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()
    record = URL(
        id=uuid.uuid4(),
        original_url="https://deleted-url.com",
        short_code="del123",
        user_id=user_id,
        is_active=True,
        expires_at=None,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)
    svc.repo.update = AsyncMock(return_value=record)

    await svc.delete_url("del123", owner_id=user_id)

    mock_redis.delete.assert_called_once_with("url_shortener:short:del123")
