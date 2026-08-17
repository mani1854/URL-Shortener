"""
schemas/url.py

Pydantic v2 schemas for URL creation, updates, and responses with rich OpenAPI examples.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    Field,
    field_validator,
)

# ── Request schemas ────────────────────────────────────────────────────────────

class URLCreateRequest(BaseModel):
    """Payload for creating a new shortened URL."""

    original_url: AnyHttpUrl = Field(
        ...,
        validation_alias=AliasChoices("url", "original_url"),
        description="The long destination URL to shorten.",
        examples=["https://fastapi.tiangolo.com/tutorial/bigger-applications/"],
    )
    custom_alias: str | None = Field(
        None,
        validation_alias=AliasChoices("custom_alias", "alias"),
        min_length=4,
        max_length=50,
        description="Optional custom slug (4-50 chars: alphanumeric, dash, underscore).",
        examples=["fastapi-docs"],
    )
    expires_at: datetime | None = Field(
        None,
        validation_alias=AliasChoices("expiry", "expires_at"),
        description="Optional UTC expiry timestamp. Must be in the future.",
        examples=["2026-12-31T23:59:59Z"],
    )
    title: str | None = Field(None, max_length=255, description="Optional title.", examples=["FastAPI Documentation"])
    description: str | None = Field(None, max_length=2000, description="Optional description.", examples=["Reference guide for larger FastAPI applications."])

    @field_validator("original_url", mode="before")
    @classmethod
    def strip_and_validate_url_str(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.strip()
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return v

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
                "url": "https://fastapi.tiangolo.com/tutorial/bigger-applications/",
                "custom_alias": "fastapi-docs",
                "expiry": "2026-12-31T23:59:59Z",
                "title": "FastAPI Guide",
            }
        }
    }


class URLUpdateRequest(BaseModel):
    """Payload for modifying an existing shortened URL."""

    original_url: AnyHttpUrl | None = Field(
        None, validation_alias=AliasChoices("url", "original_url"),
        description="New destination URL.",
        examples=["https://fastapi.tiangolo.com/advanced/"],
    )
    expires_at: datetime | None = Field(
        None, validation_alias=AliasChoices("expiry", "expires_at"),
        description="New expiration timestamp or null to remove expiry.",
        examples=["2027-01-01T00:00:00Z"],
    )
    is_active: bool | None = Field(None, description="Enable or disable redirect.", examples=[True])
    title: str | None = Field(None, max_length=255, description="Updated title.", examples=["Updated Title"])
    description: str | None = Field(None, max_length=2000, description="Updated description.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://fastapi.tiangolo.com/advanced/",
                "title": "Advanced FastAPI Guide",
                "is_active": True,
            }
        }
    }


# ── Response schemas ───────────────────────────────────────────────────────────

class URLShortenResponse(BaseModel):
    """Concise creation response."""

    short_url: str = Field(description="Fully qualified short URL.", examples=["http://localhost:8000/fastapi-docs"])
    short_code: str = Field(description="Unique short code slug.", examples=["fastapi-docs"])
    original_url: str = Field(description="Long destination URL.")
    expires_at: datetime | None = None


class URLResponse(BaseModel):
    """Detailed short URL representation."""

    id: uuid.UUID = Field(description="Unique record UUID.")
    original_url: str = Field(description="Original destination URL.")
    short_code: str = Field(description="Short code slug.")
    short_url: str = Field(description="Fully qualified shortened URL.")
    user_id: uuid.UUID | None = Field(None, description="Owning user UUID (null for anonymous).")
    title: str | None = None
    description: str | None = None
    is_active: bool = Field(description="Active state.")
    is_custom: bool = Field(description="True if custom alias was specified.")
    click_count: int = Field(description="Total redirects served.")
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "7b844f22-d027-4a0b-967b-1fc2776c5b02",
                "original_url": "https://fastapi.tiangolo.com/tutorial/bigger-applications/",
                "short_code": "fastapi-docs",
                "short_url": "http://localhost:8000/fastapi-docs",
                "user_id": "e7b0a8c2-4b72-4b7b-83bb-1e4e3f43a512",
                "title": "FastAPI Guide",
                "is_active": True,
                "is_custom": True,
                "click_count": 1420,
                "expires_at": "2026-12-31T23:59:59Z",
                "created_at": "2026-08-17T12:00:00Z",
                "updated_at": "2026-08-17T12:00:00Z",
            }
        },
    }


class URLListResponse(BaseModel):
    """Paginated list of URLs."""

    items: list[URLResponse]
    total: int = Field(description="Total items count.")
    page: int = Field(description="Current page.")
    page_size: int = Field(description="Items per page.")
    has_next: bool = Field(description="Next page availability.")


class URLStatsResponse(BaseModel):
    """High-level summary click metrics for a short URL."""

    short_code: str = Field(description="Short code slug.")
    click_count: int = Field(description="Total clicks recorded.")
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
