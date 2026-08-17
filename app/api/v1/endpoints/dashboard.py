"""
api/v1/endpoints/dashboard.py

User Dashboard REST endpoints.
Allows authenticated users to list their shortened URLs with pagination,
update expiration timestamps, and soft-delete/deactivate their links.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.auth import get_current_active_user
from app.dependencies.services import get_url_service
from app.models.user import User
from app.schemas.common import APIResponse, ErrorResponse
from app.schemas.dashboard import (
    PaginatedUserURLsResponse,
    UpdateExpiryRequest,
    UserURLItem,
)
from app.services.url_service import URLService

router = APIRouter(prefix="/my-urls", tags=["Dashboard"])


# ── GET /my-urls ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=APIResponse[PaginatedUserURLsResponse],
    summary="List My URLs",
    description=(
        "Retrieve a paginated list of all shortened URLs owned by the authenticated user. "
        "Includes original URL, short URL, total click count, expiry, and created date."
    ),
    responses={
        200: {"description": "Paginated list of user URLs."},
        401: {"model": ErrorResponse, "description": "Authentication required."},
        429: {"model": ErrorResponse, "description": "Rate limit quota exceeded."},
    },
)
async def list_my_urls(
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Number of items per page."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[PaginatedUserURLsResponse]:
    """
    GET /api/v1/my-urls
    Returns paginated URLs owned by the current user.
    """
    result = await svc.list_dashboard_urls(
        owner_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return APIResponse(data=result, message="User URLs retrieved successfully.")


# ── PATCH /my-urls/{short_code} ───────────────────────────────────────────────

@router.patch(
    "/{short_code}",
    response_model=APIResponse[UserURLItem],
    summary="Update URL Expiry",
    description="Update the expiry date for a shortened URL owned by the authenticated user.",
    responses={
        200: {"description": "URL expiry timestamp updated successfully."},
        400: {"model": ErrorResponse, "description": "Expiry timestamp must be in the future."},
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Permission denied (not the link owner)."},
        404: {"model": ErrorResponse, "description": "Short URL not found."},
        422: {"model": ErrorResponse, "description": "Validation error in request payload."},
        429: {"model": ErrorResponse, "description": "Rate limit quota exceeded."},
    },
)
async def update_my_url_expiry(
    payload: UpdateExpiryRequest,
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code to update."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[UserURLItem]:
    """
    PATCH /api/v1/my-urls/{short_code}
    Update or remove expiration date on a user's link and evict cache.
    """
    updated_item = await svc.update_url_expiry(
        short_code=short_code,
        new_expiry=payload.expires_at,
        owner_id=current_user.id,
    )
    return APIResponse(data=updated_item, message="URL expiry updated successfully.")


# ── DELETE /my-urls/{short_code} ──────────────────────────────────────────────

@router.delete(
    "/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete My URL",
    description="Soft-delete a shortened URL owned by the authenticated user and evict from cache.",
    responses={
        204: {"description": "URL deactivated and evicted from cache."},
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Permission denied (not the link owner)."},
        404: {"model": ErrorResponse, "description": "Short URL not found."},
        429: {"model": ErrorResponse, "description": "Rate limit quota exceeded."},
    },
)
async def delete_my_url(
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code to delete."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> None:
    """
    DELETE /api/v1/my-urls/{short_code}
    Deactivate URL and purge from Redis cache.
    """
    await svc.delete_url(short_code=short_code, owner_id=current_user.id)
