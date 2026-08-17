"""
schemas/analytics.py

Pydantic v2 schemas for URL analytics and distribution breakdowns with OpenAPI examples.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DailyClickItem(BaseModel):
    """Aggregated clicks for a single day."""

    date: str = Field(description="Date in YYYY-MM-DD format.", examples=["2026-08-17"])
    count: int = Field(description="Total clicks on this day.", examples=[125])


class DistributionItem(BaseModel):
    """Generic category distribution item."""

    label: str = Field(description="Category label (e.g., country, browser, device).", examples=["Chrome"])
    count: int = Field(description="Click count for this category.", examples=[350])
    percentage: float = Field(description="Percentage of total clicks.", examples=[70.0])


class CountryDistributionItem(BaseModel):
    """Country breakdown item."""

    country: str = Field(description="Two-letter ISO country code or 'Unknown'.", examples=["US"])
    count: int = Field(description="Clicks from this country.", examples=[450])
    percentage: float = Field(description="Percentage of total clicks.", examples=[60.0])


class BrowserDistributionItem(BaseModel):
    """Browser breakdown item."""

    browser: str = Field(description="Browser family name.", examples=["Chrome"])
    count: int = Field(description="Clicks from this browser.", examples=[500])
    percentage: float = Field(description="Percentage of total clicks.", examples=[66.67])


class DeviceDistributionItem(BaseModel):
    """Device breakdown item."""

    device_type: str = Field(description="Device category: desktop, mobile, tablet, bot, etc.", examples=["desktop"])
    count: int = Field(description="Clicks from this device category.", examples=[550])
    percentage: float = Field(description="Percentage of total clicks.", examples=[73.33])


class AnalyticsResponse(BaseModel):
    """Complete analytics response payload for GET /analytics/{short_code}."""

    short_code: str = Field(description="Short code slug.", examples=["fastapi-docs"])
    original_url: str = Field(description="Long destination URL.", examples=["https://fastapi.tiangolo.com"])
    total_clicks: int = Field(description="Total lifetime clicks.", examples=[750])
    daily_clicks: list[DailyClickItem] = Field(default_factory=list, description="Daily time-series click counts.")
    country_distribution: list[CountryDistributionItem] = Field(default_factory=list, description="Geographical click breakdown.")
    browser_distribution: list[BrowserDistributionItem] = Field(default_factory=list, description="Browser client breakdown.")
    device_distribution: list[DeviceDistributionItem] = Field(default_factory=list, description="Device platform breakdown.")
    created_at: datetime = Field(description="Short URL creation timestamp.")
    expires_at: datetime | None = Field(None, description="Expiration date (if set).")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "short_code": "fastapi-docs",
                "original_url": "https://fastapi.tiangolo.com",
                "total_clicks": 750,
                "daily_clicks": [
                    {"date": "2026-08-17", "count": 125},
                    {"date": "2026-08-16", "count": 98},
                ],
                "country_distribution": [
                    {"country": "US", "count": 450, "percentage": 60.0},
                    {"country": "IN", "count": 150, "percentage": 20.0},
                    {"country": "DE", "count": 150, "percentage": 20.0},
                ],
                "browser_distribution": [
                    {"browser": "Chrome", "count": 500, "percentage": 66.67},
                    {"browser": "Safari", "count": 150, "percentage": 20.0},
                    {"browser": "Firefox", "count": 100, "percentage": 13.33},
                ],
                "device_distribution": [
                    {"device_type": "desktop", "count": 550, "percentage": 73.33},
                    {"device_type": "mobile", "count": 200, "percentage": 26.67},
                ],
                "created_at": "2026-08-17T10:00:00Z",
                "expires_at": None,
            }
        },
    }
