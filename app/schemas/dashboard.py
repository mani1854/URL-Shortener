"""
schemas/dashboard.py

Pydantic v2 schemas for User Dashboard APIs with rich OpenAPI examples.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator


class UserURLItem(BaseModel):
    """
    Representation of a user's shortened URL in the dashboard.
    Includes original URL, short URL, click counter, expiry, and created date.
    """

    id: uuid.UUID = Field(description="Unique record UUID.")
    original_url: str = Field(description="Original destination URL.", examples=["https://github.com/fastapi/fastapi"])
    short_url: str = Field(description="Fully qualified short URL.", examples=["http://localhost:8000/fastapi-repo"])
    short_code: str = Field(description="Short code slug.", examples=["fastapi-repo"])
    clicks: int = Field(description="Total click count.", examples=[350])
    expiry: datetime | None = Field(None, description="Expiration date in UTC (if set).", examples=["2026-12-31T23:59:59Z"])
    created_date: datetime = Field(description="Creation date in UTC.", examples=["2026-08-17T12:00:00Z"])
    title: str | None = Field(None, description="Optional title label.", examples=["FastAPI GitHub"])
    is_active: bool = Field(True, description="Active status.")
    is_custom: bool = Field(False, description="True if custom alias was chosen.")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "7b844f22-d027-4a0b-967b-1fc2776c5b02",
                "original_url": "https://github.com/fastapi/fastapi",
                "short_url": "http://localhost:8000/fastapi-repo",
                "short_code": "fastapi-repo",
                "clicks": 350,
                "expiry": "2026-12-31T23:59:59Z",
                "created_date": "2026-08-17T12:00:00Z",
                "title": "FastAPI GitHub",
                "is_active": True,
                "is_custom": True,
            }
        },
    }


class PaginatedUserURLsResponse(BaseModel):
    """Paginated list envelope for user's shortened URLs."""

    items: list[UserURLItem] = Field(description="List of URL items for the current page.")
    total: int = Field(description="Total number of URLs owned by user.", examples=[45])
    page: int = Field(description="Current page number (1-indexed).", examples=[1])
    page_size: int = Field(description="Number of items per page.", examples=[20])
    total_pages: int = Field(description="Total available pages.", examples=[3])
    has_next: bool = Field(description="True if a next page exists.", examples=[True])
    has_prev: bool = Field(description="True if a previous page exists.", examples=[False])

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [
                    {
                        "id": "7b844f22-d027-4a0b-967b-1fc2776c5b02",
                        "original_url": "https://github.com/fastapi/fastapi",
                        "short_url": "http://localhost:8000/fastapi-repo",
                        "short_code": "fastapi-repo",
                        "clicks": 350,
                        "expiry": None,
                        "created_date": "2026-08-17T12:00:00Z",
                        "title": "FastAPI GitHub",
                        "is_active": True,
                        "is_custom": True,
                    }
                ],
                "total": 45,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "has_next": True,
                "has_prev": False,
            }
        }
    }


class UpdateExpiryRequest(BaseModel):
    """Payload for updating a short URL's expiry timestamp."""

    expires_at: datetime | None = Field(
        None,
        validation_alias=AliasChoices("expiry", "expires_at"),
        description="New future UTC timestamp, or null to remove expiry.",
        examples=["2027-01-01T00:00:00Z"],
    )

    @field_validator("expires_at")
    @classmethod
    def validate_future_expiry(cls, v: datetime | None) -> datetime | None:
        if v is not None:
            now_utc = datetime.now(UTC)
            compare_dt = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
            if compare_dt <= now_utc:
                raise ValueError("Expiry timestamp must be in the future.")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "expiry": "2027-01-01T00:00:00Z",
            }
        }
    }
