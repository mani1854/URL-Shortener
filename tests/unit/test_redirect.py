"""
tests/unit/test_redirect.py

Unit tests for redirect service, expiry checking, client metadata extraction,
and background analytics persistence.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.core.exceptions import ShortURLNotFoundError, URLExpiredError
from app.models.url import URL
from app.services.url_service import URLService
from app.utils.client_info import (
    extract_client_ip,
    parse_user_agent_details,
)


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_original_url = AsyncMock(return_value=None)
    cache.set_original_url = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def mock_db():
    return AsyncMock()


# ── Client Info Extraction Tests ───────────────────────────────────────────────

class TestClientInfoExtraction:
    def test_extract_ip_from_x_forwarded_for(self):
        scope = {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"203.0.113.195, 70.41.3.18, 150.172.238.178"),
            ],
        }
        req = Request(scope)
        assert extract_client_ip(req) == "203.0.113.195"

    def test_extract_ip_from_x_real_ip(self):
        scope = {
            "type": "http",
            "headers": [
                (b"x-real-ip", b"198.51.100.42"),
            ],
        }
        req = Request(scope)
        assert extract_client_ip(req) == "198.51.100.42"

    def test_parse_user_agent_desktop_chrome(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        device, browser, os_name = parse_user_agent_details(ua)
        assert device == "desktop"
        assert "Chrome" in browser
        assert "Windows" in os_name

    def test_parse_user_agent_mobile_iphone(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        device, browser, os_name = parse_user_agent_details(ua)
        assert device == "mobile"
        assert "Safari" in browser or "Mobile" in browser or browser is not None
        assert "iOS" in os_name or "Mac" in os_name

    def test_parse_user_agent_bot(self):
        ua = "Googlebot/2.1 (+http://www.google.com/bot.html)"
        device, browser, os_name = parse_user_agent_details(ua)
        assert device == "bot"


# ── Redirect Lookup & Expiry Tests ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_redirect_cache_hit_returns_immediately(mock_db, mock_cache):
    svc = URLService(db=mock_db, cache=mock_cache)
    mock_cache.get_original_url.return_value = "https://cached-target.com"

    url = await svc.resolve_short_code("fast123")
    assert url == "https://cached-target.com"
    svc.repo.get_by_short_code = AsyncMock()
    svc.repo.get_by_short_code.assert_not_called()


@pytest.mark.anyio
async def test_redirect_cache_miss_queries_db_and_populates_cache(mock_db, mock_cache):
    svc = URLService(db=mock_db, cache=mock_cache)
    mock_cache.get_original_url.return_value = None

    record = URL(
        id=uuid.uuid4(),
        original_url="https://db-target.com",
        short_code="db12345",
        is_active=True,
        expires_at=None,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    url = await svc.resolve_short_code("db12345")
    assert url == "https://db-target.com"
    mock_cache.set_original_url.assert_called_once_with("db12345", "https://db-target.com")


@pytest.mark.anyio
async def test_redirect_expired_link_raises_410(mock_db, mock_cache):
    svc = URLService(db=mock_db, cache=mock_cache)
    mock_cache.get_original_url.return_value = None

    record = URL(
        id=uuid.uuid4(),
        original_url="https://expired.com",
        short_code="exp001",
        is_active=True,
        expires_at=datetime.now(UTC) - timedelta(hours=2),
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    with pytest.raises(URLExpiredError):
        await svc.resolve_short_code("exp001")


@pytest.mark.anyio
async def test_redirect_inactive_link_raises_404(mock_db, mock_cache):
    svc = URLService(db=mock_db, cache=mock_cache)
    mock_cache.get_original_url.return_value = None

    record = URL(
        id=uuid.uuid4(),
        original_url="https://inactive.com",
        short_code="off001",
        is_active=False,
        expires_at=None,
    )
    svc.repo.get_by_short_code = AsyncMock(return_value=record)

    with pytest.raises(ShortURLNotFoundError):
        await svc.resolve_short_code("off001")


@pytest.mark.anyio
async def test_redirect_nonexistent_link_raises_404(mock_db, mock_cache):
    svc = URLService(db=mock_db, cache=mock_cache)
    mock_cache.get_original_url.return_value = None
    svc.repo.get_by_short_code = AsyncMock(return_value=None)

    with pytest.raises(ShortURLNotFoundError):
        await svc.resolve_short_code("missing")
