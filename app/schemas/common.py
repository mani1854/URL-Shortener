"""
schemas/common.py

Shared response envelopes, error models, and health schemas with OpenAPI examples.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """
    Standard API response envelope.
    Ensures all endpoints return a consistent, uniform JSON shape.
    """

    success: bool = Field(True, description="Indicates if the request was successful.")
    data: DataT | None = Field(None, description="Response payload data.")
    message: str | None = Field(None, description="Optional human-readable informational message.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "data": {"key": "value"},
                "message": "Operation completed successfully.",
            }
        }
    }


class ErrorDetail(BaseModel):
    """A single validation or domain error item."""

    field: str | None = Field(None, description="Target field that caused the error (if applicable).")
    message: str = Field(..., description="Descriptive error explanation.")
    code: str | None = Field(None, description="Machine-readable error classification code.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "field": "url",
                "message": "The provided URL is not valid.",
                "code": "invalid_url",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standardized error envelope returned on all 4xx / 5xx responses."""

    success: bool = Field(False, description="Always false for error responses.")
    errors: list[ErrorDetail] = Field(..., description="List of specific error details.")
    request_id: str | None = Field(None, description="Unique correlation ID for tracing.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "errors": [
                    {
                        "field": "custom_alias",
                        "message": "The requested custom alias is already taken.",
                        "code": "alias_conflict",
                    }
                ],
                "request_id": "c7a8b419-74d1-4e92-8025-0d297a7e8f52",
            }
        }
    }


class HealthResponse(BaseModel):
    """System health check and dependency connectivity response."""

    status: str = Field("ok", description="Overall health status: 'ok' or 'degraded'.")
    version: str = Field(..., description="Current running application version.")
    environment: str = Field(..., description="Deployment environment (development, staging, production).")
    db: str = Field("ok", description="PostgreSQL async database connection state.")
    redis: str = Field("ok", description="Redis cache connectivity state.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "ok",
                "version": "1.0.0",
                "environment": "production",
                "db": "ok",
                "redis": "ok",
            }
        }
    }
