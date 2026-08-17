"""
services/analytics_service.py

Business-logic layer for click analytics collection, aggregation, and time-series reporting.

Aggregations:
  - Total click volume
  - Daily time-series breakdown
  - Geographic distribution (country code)
  - Browser distribution
  - Device platform distribution
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError, ShortURLNotFoundError
from app.models.click_analytics import ClickAnalytics
from app.schemas.analytics import (
    AnalyticsResponse,
    BrowserDistributionItem,
    CountryDistributionItem,
    DailyClickItem,
    DeviceDistributionItem,
)
from app.services.url_service import URLRepository

logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """Repository handling analytical aggregations on ClickAnalytics table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_total_clicks(self, url_id: uuid.UUID) -> int:
        """Fetch total recorded click rows for a URL."""
        result = await self.session.execute(
            select(func.count()).select_from(ClickAnalytics).where(ClickAnalytics.url_id == url_id)
        )
        return result.scalar() or 0

    async def get_daily_clicks(self, url_id: uuid.UUID, *, limit: int = 30) -> list[DailyClickItem]:
        """Fetch daily click totals ordered by date."""
        date_col = cast(ClickAnalytics.timestamp, Date).label("click_date")
        stmt = (
            select(date_col, func.count(ClickAnalytics.id).label("count"))
            .where(ClickAnalytics.url_id == url_id)
            .group_by(date_col)
            .order_by(desc("click_date"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            DailyClickItem(
                date=str(row.click_date),
                count=int(row.count),
            )
            for row in rows
        ]

    async def get_country_distribution(
        self, url_id: uuid.UUID, *, total: int, limit: int = 10
    ) -> list[CountryDistributionItem]:
        """Fetch country distribution breakdown."""
        country_col = func.coalesce(ClickAnalytics.country, "Unknown").label("country_label")
        stmt = (
            select(country_col, func.count(ClickAnalytics.id).label("count"))
            .where(ClickAnalytics.url_id == url_id)
            .group_by(country_col)
            .order_by(desc("count"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            CountryDistributionItem(
                country=str(row.country_label),
                count=int(row.count),
                percentage=round((int(row.count) / total * 100), 2) if total > 0 else 0.0,
            )
            for row in rows
        ]

    async def get_browser_distribution(
        self, url_id: uuid.UUID, *, total: int, limit: int = 10
    ) -> list[BrowserDistributionItem]:
        """Fetch browser family distribution breakdown."""
        browser_col = func.coalesce(ClickAnalytics.browser, "Other").label("browser_label")
        stmt = (
            select(browser_col, func.count(ClickAnalytics.id).label("count"))
            .where(ClickAnalytics.url_id == url_id)
            .group_by(browser_col)
            .order_by(desc("count"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            BrowserDistributionItem(
                browser=str(row.browser_label),
                count=int(row.count),
                percentage=round((int(row.count) / total * 100), 2) if total > 0 else 0.0,
            )
            for row in rows
        ]

    async def get_device_distribution(
        self, url_id: uuid.UUID, *, total: int, limit: int = 10
    ) -> list[DeviceDistributionItem]:
        """Fetch device type distribution breakdown."""
        device_col = func.coalesce(ClickAnalytics.device_type, "desktop").label("device_label")
        stmt = (
            select(device_col, func.count(ClickAnalytics.id).label("count"))
            .where(ClickAnalytics.url_id == url_id)
            .group_by(device_col)
            .order_by(desc("count"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            DeviceDistributionItem(
                device_type=str(row.device_label),
                count=int(row.count),
                percentage=round((int(row.count) / total * 100), 2) if total > 0 else 0.0,
            )
            for row in rows
        ]


class AnalyticsService:
    """High-level service coordinating URL analytics retrieval."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.url_repo = URLRepository(db)
        self.analytics_repo = AnalyticsRepository(db)

    async def get_url_analytics(
        self,
        short_code: str,
        *,
        owner_id: uuid.UUID | str | None = None,
    ) -> AnalyticsResponse:
        """
        Retrieve comprehensive click analytics for a given short URL.

        Raises:
            ShortURLNotFoundError: If short URL does not exist or is inactive.
            PermissionDeniedError: If link is owned by another user.
        """
        record = await self.url_repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()

        # Check ownership if specified
        if owner_id is not None and record.user_id is not None:
            user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
            if record.user_id != user_uuid:
                raise PermissionDeniedError()

        # Gather aggregated analytics
        total_clicks = record.click_count or await self.analytics_repo.get_total_clicks(record.id)
        effective_total = total_clicks if total_clicks > 0 else 1

        daily_clicks = await self.analytics_repo.get_daily_clicks(record.id, limit=30)
        country_dist = await self.analytics_repo.get_country_distribution(
            record.id, total=effective_total, limit=10
        )
        browser_dist = await self.analytics_repo.get_browser_distribution(
            record.id, total=effective_total, limit=10
        )
        device_dist = await self.analytics_repo.get_device_distribution(
            record.id, total=effective_total, limit=10
        )

        return AnalyticsResponse(
            short_code=record.short_code,
            original_url=record.original_url,
            total_clicks=record.click_count,
            daily_clicks=daily_clicks,
            country_distribution=country_dist,
            browser_distribution=browser_dist,
            device_distribution=device_dist,
            created_at=record.created_at or datetime.now(UTC),
            expires_at=record.expires_at,
        )
