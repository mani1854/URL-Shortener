"""
api/v1/endpoints/analytics.py

Analytics REST endpoints.
Provides click statistics, daily time-series, country, browser, and device breakdowns.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from app.dependencies.auth import get_optional_user
from app.dependencies.services import get_analytics_service
from app.models.user import User
from app.schemas.analytics import AnalyticsResponse
from app.schemas.common import APIResponse, ErrorResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get(
    "/{short_code}",
    response_model=APIResponse[AnalyticsResponse],
    summary="Get URL Click Analytics",
    description=(
        "Retrieve aggregated click statistics for a short URL: "
        "total clicks, daily time-series, country distribution, "
        "browser distribution, and device platform distribution."
    ),
    responses={
        200: {"description": "Click analytics retrieved successfully."},
        403: {"model": ErrorResponse, "description": "Permission denied (link belongs to another private user)."},
        404: {"model": ErrorResponse, "description": "Short URL not found or inactive."},
        429: {"model": ErrorResponse, "description": "Rate limit quota exceeded."},
    },
)
async def get_url_analytics(
    short_code: str = Path(..., min_length=4, max_length=50, description="Short URL code or custom alias."),
    current_user: User | None = Depends(get_optional_user),
    svc: AnalyticsService = Depends(get_analytics_service),
) -> APIResponse[AnalyticsResponse]:
    """
    GET /api/v1/analytics/{short_code}
    Returns detailed metrics and breakdowns for the specified short URL.
    """
    owner_id = current_user.id if current_user else None
    analytics_data = await svc.get_url_analytics(short_code, owner_id=owner_id)
    return APIResponse(data=analytics_data, message="Analytics retrieved successfully.")
