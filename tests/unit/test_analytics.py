"""
tests/unit/test_analytics.py

Unit tests for GeoIP lookup, analytics aggregations (daily, country, browser, device),
and analytics service business logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import PermissionDeniedError, ShortURLNotFoundError
from app.models.url import URL
from app.schemas.analytics import (
    BrowserDistributionItem,
    CountryDistributionItem,
    DailyClickItem,
    DeviceDistributionItem,
)
from app.services.analytics_service import AnalyticsService
from app.utils.geoip import is_private_or_reserved_ip, lookup_ip_geolocation

# ── GeoIP Unit Tests ──────────────────────────────────────────────────────────

class TestGeoIPUtils:
    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.0.0.1",
            "192.168.1.100",
            "172.16.0.1",
            "::1",
            "invalid-ip",
        ],
    )
    def test_private_or_reserved_ip_detection(self, ip: str):
        assert is_private_or_reserved_ip(ip) is True

    def test_public_ip_is_not_private(self):
        assert is_private_or_reserved_ip("8.8.8.8") is False
        assert is_private_or_reserved_ip("1.1.1.1") is False

    @pytest.mark.anyio
    async def test_lookup_private_ip_returns_none(self):
        country, city = await lookup_ip_geolocation("127.0.0.1")
        assert country is None
        assert city is None

    @pytest.mark.anyio
    async def test_lookup_public_ip_mocked_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "countryCode": "US",
            "city": "Ashburn",
        }
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            country, city = await lookup_ip_geolocation("93.184.216.34")
            assert country == "US"
            assert city == "Ashburn"


# ── AnalyticsService Unit Tests ───────────────────────────────────────────────

@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.anyio
async def test_get_url_analytics_success(mock_db):
    svc = AnalyticsService(db=mock_db)

    fake_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    record = URL(
        id=fake_id,
        original_url="https://analytics-target.com",
        short_code="stat123",
        user_id=user_id,
        is_active=True,
        click_count=150,
        created_at=now,
    )
    svc.url_repo.get_by_short_code = AsyncMock(return_value=record)

    # Mock aggregation repository queries
    svc.analytics_repo.get_daily_clicks = AsyncMock(
        return_value=[
            DailyClickItem(date="2026-08-17", count=100),
            DailyClickItem(date="2026-08-16", count=50),
        ]
    )
    svc.analytics_repo.get_country_distribution = AsyncMock(
        return_value=[
            CountryDistributionItem(country="US", count=90, percentage=60.0),
            CountryDistributionItem(country="IN", count=60, percentage=40.0),
        ]
    )
    svc.analytics_repo.get_browser_distribution = AsyncMock(
        return_value=[
            BrowserDistributionItem(browser="Chrome", count=120, percentage=80.0),
            BrowserDistributionItem(browser="Safari", count=30, percentage=20.0),
        ]
    )
    svc.analytics_repo.get_device_distribution = AsyncMock(
        return_value=[
            DeviceDistributionItem(device_type="desktop", count=100, percentage=66.67),
            DeviceDistributionItem(device_type="mobile", count=50, percentage=33.33),
        ]
    )

    analytics = await svc.get_url_analytics("stat123", owner_id=user_id)

    assert analytics.short_code == "stat123"
    assert analytics.total_clicks == 150
    assert len(analytics.daily_clicks) == 2
    assert analytics.daily_clicks[0].count == 100
    assert analytics.country_distribution[0].country == "US"
    assert analytics.browser_distribution[0].browser == "Chrome"
    assert analytics.device_distribution[0].device_type == "desktop"


@pytest.mark.anyio
async def test_get_url_analytics_not_found(mock_db):
    svc = AnalyticsService(db=mock_db)
    svc.url_repo.get_by_short_code = AsyncMock(return_value=None)

    with pytest.raises(ShortURLNotFoundError):
        await svc.get_url_analytics("missing-code")


@pytest.mark.anyio
async def test_get_url_analytics_permission_denied(mock_db):
    svc = AnalyticsService(db=mock_db)
    owner_a = uuid.uuid4()
    owner_b = uuid.uuid4()

    record = URL(
        id=uuid.uuid4(),
        original_url="https://target.com",
        short_code="private123",
        user_id=owner_a,
        is_active=True,
    )
    svc.url_repo.get_by_short_code = AsyncMock(return_value=record)

    with pytest.raises(PermissionDeniedError):
        await svc.get_url_analytics("private123", owner_id=owner_b)
