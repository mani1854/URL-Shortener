"""
tests/unit/test_dashboard.py

Unit tests for User Dashboard functionality:
  - GET /my-urls pagination calculation (total, page, page_size, total_pages, has_next, has_prev)
  - PATCH /my-urls/{short_code} expiry updates and cache eviction
  - DELETE /my-urls/{short_code} soft-deletion, cache eviction, and authorization checks
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import PermissionDeniedError
from app.models.url import URL
from app.services.url_service import URLService
from app.utils.cache import CacheClient


@pytest.fixture
def mock_redis():
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    return redis_mock


@pytest.fixture
def cache_client(mock_redis):
    return CacheClient(mock_redis)


@pytest.fixture
def mock_db():
    return AsyncMock()


# ── Dashboard Listing & Pagination Unit Tests ─────────────────────────────────

@pytest.mark.anyio
async def test_list_dashboard_urls_pagination(mock_db, cache_client):
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    # 25 total records, requesting page 1 with page_size 10
    fake_records = [
        URL(
            id=uuid.uuid4(),
            original_url=f"https://example{i}.com",
            short_code=f"code{i:03d}",
            user_id=user_id,
            is_active=True,
            is_custom=False,
            click_count=i * 5,
            expires_at=None,
            created_at=now,
            updated_at=now,
        )
        for i in range(10)
    ]
    svc.repo.list_by_owner = AsyncMock(return_value=(fake_records, 25))

    res = await svc.list_dashboard_urls(owner_id=user_id, page=1, page_size=10)

    assert len(res.items) == 10
    assert res.total == 25
    assert res.page == 1
    assert res.page_size == 10
    assert res.total_pages == 3
    assert res.has_next is True
    assert res.has_prev is False

    # Check required item fields
    item = res.items[0]
    assert item.original_url == "https://example0.com"
    assert item.short_code == "code000"
    assert item.clicks == 0
    assert item.expiry is None
    assert item.created_date == now


@pytest.mark.anyio
async def test_list_dashboard_urls_middle_page(mock_db, cache_client):
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    fake_records = [
        URL(
            id=uuid.uuid4(),
            original_url=f"https://example{i}.com",
            short_code=f"code{i:03d}",
            user_id=user_id,
            is_active=True,
            click_count=10,
            created_at=now,
        )
        for i in range(10)
    ]
    svc.repo.list_by_owner = AsyncMock(return_value=(fake_records, 25))

    res = await svc.list_dashboard_urls(owner_id=user_id, page=2, page_size=10)

    assert res.page == 2
    assert res.total_pages == 3
    assert res.has_next is True
    assert res.has_prev is True


# ── Expiry Update Unit Tests ──────────────────────────────────────────────────

@pytest.mark.anyio
async def test_update_url_expiry_success(mock_db, cache_client, mock_redis):
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()
    future_date = datetime.now(UTC) + timedelta(days=30)

    record = URL(
        id=uuid.uuid4(),
        original_url="https://docs.fastapi.tiangolo.com",
        short_code="fastapi1",
        user_id=user_id,
        is_active=True,
        click_count=42,
        expires_at=None,
        created_at=datetime.now(UTC),
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    updated_record = URL(
        id=record.id,
        original_url=record.original_url,
        short_code=record.short_code,
        user_id=user_id,
        is_active=True,
        click_count=42,
        expires_at=future_date,
        created_at=record.created_at,
    )
    svc.repo.update = AsyncMock(return_value=updated_record)

    result = await svc.update_url_expiry("fastapi1", future_date, owner_id=user_id)

    assert result.short_code == "fastapi1"
    assert result.expiry == future_date
    assert result.clicks == 42
    # Verify cache eviction
    mock_redis.delete.assert_called_once_with("url_shortener:short:fastapi1")


@pytest.mark.anyio
async def test_update_url_expiry_unauthorized_raises_403(mock_db, cache_client):
    svc = URLService(db=mock_db, cache=cache_client)
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()

    record = URL(
        id=uuid.uuid4(),
        original_url="https://private.com",
        short_code="priv001",
        user_id=owner_a,
        is_active=True,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    with pytest.raises(PermissionDeniedError):
        await svc.update_url_expiry("priv001", datetime.now(UTC), owner_id=owner_b)


# ── Delete URL Unit Tests ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_delete_url_success(mock_db, cache_client, mock_redis):
    svc = URLService(db=mock_db, cache=cache_client)
    user_id = uuid.uuid4()

    record = URL(
        id=uuid.uuid4(),
        original_url="https://to-delete.com",
        short_code="del001",
        user_id=user_id,
        is_active=True,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)
    svc.repo.update = AsyncMock(return_value=record)

    await svc.delete_url("del001", owner_id=user_id)

    # Soft delete check and cache eviction
    svc.repo.update.assert_called_once_with(record, is_active=False)
    mock_redis.delete.assert_called_once_with("url_shortener:short:del001")


@pytest.mark.anyio
async def test_delete_url_unauthorized_raises_403(mock_db, cache_client):
    svc = URLService(db=mock_db, cache=cache_client)
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()

    record = URL(
        id=uuid.uuid4(),
        original_url="https://victim.com",
        short_code="victim1",
        user_id=owner_a,
        is_active=True,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    with pytest.raises(PermissionDeniedError):
        await svc.delete_url("victim1", owner_id=owner_b)
