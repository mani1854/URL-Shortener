"""
api/v1/endpoints/urls.py

URL shortener REST endpoints.
All business logic is delegated to URLService (injected via dependency injection).
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Query, Request, status
from fastapi.responses import RedirectResponse

from app.dependencies.auth import get_current_active_user, get_optional_user
from app.dependencies.services import get_url_service
from app.models.user import User
from app.schemas.common import APIResponse, ErrorResponse
from app.schemas.url import (
    URLCreateRequest,
    URLListResponse,
    URLResponse,
    URLUpdateRequest,
)
from app.services.url_service import URLService, record_background_click
from app.utils.client_info import extract_client_info

router = APIRouter()


# ── Create / Shorten ───────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[URLResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Shorten a URL",
    description=(
        "Creates a new shortened URL with collision-resistant Base62 code or optional custom alias. "
        "Supports future expiration timestamps and auto-associates with the logged-in user if authenticated."
    ),
    responses={
        201: {"description": "Short URL created successfully."},
        400: {"model": ErrorResponse, "description": "Invalid URL scheme or format."},
        409: {"model": ErrorResponse, "description": "Custom alias already in use."},
        422: {"model": ErrorResponse, "description": "Request validation error."},
        429: {"model": ErrorResponse, "description": "Rate limit quota exceeded."},
    },
)
@router.post(
    "/shorten",
    response_model=APIResponse[URLResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Shorten a URL (convenience alias)",
    description="Convenience alias endpoint for URL shortening.",
    include_in_schema=False,
)
async def create_short_url(
    payload: URLCreateRequest,
    current_user: User | None = Depends(get_optional_user),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[URLResponse]:
    """
    POST /api/v1/urls
    Creates a new short URL. Automatically links to the authenticated user if logged in.
    """
    owner_id = current_user.id if current_user else None
    url = await svc.create_short_url(payload, owner_id=owner_id)
    return APIResponse(data=url, message="Short URL created successfully.")


# ── List ───────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=APIResponse[URLListResponse],
    summary="List URLs",
    description="Returns a paginated list of short URLs owned by the authenticated user.",
    responses={
        200: {"description": "URLs retrieved successfully."},
        401: {"model": ErrorResponse, "description": "Missing or invalid Bearer access token."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def list_urls(
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Items per page."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[URLListResponse]:
    """GET /api/v1/urls – list URLs for the current user."""
    result = await svc.list_urls(owner_id=current_user.id, page=page, page_size=page_size)
    return APIResponse(data=result)


# ── Redirect ───────────────────────────────────────────────────────────────────

@router.get(
    "/{short_code}/redirect",
    summary="Redirect to original URL",
    description=(
        "Resolves the short code via Redis cache-aside (or PostgreSQL fallback), "
        "enqueues background analytics telemetry (IP, GeoIP country, User-Agent device/browser/OS), "
        "and issues an HTTP 302 redirect."
    ),
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    responses={
        302: {"description": "Redirects to destination URL."},
        404: {"model": ErrorResponse, "description": "Short code does not exist or is inactive."},
        410: {"model": ErrorResponse, "description": "Short URL has expired."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def redirect_to_original(
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code slug."),
    request: Request = None,  # type: ignore[assignment]
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
    svc: URLService = Depends(get_url_service),
) -> RedirectResponse:
    """
    GET /api/v1/urls/{short_code}/redirect
    Lookup short code, verify expiry, record click analytics asynchronously, and redirect.
    """
    target_url = await svc.resolve_short_code(short_code)

    # Collect client info and schedule asynchronous analytics recording
    if request and background_tasks:
        client_info = extract_client_info(request)
        background_tasks.add_task(
            record_background_click,
            short_code=short_code,
            ip_address=client_info.ip_address,
            user_agent=client_info.user_agent,
            referer=client_info.referer,
            device_type=client_info.device_type,
            browser=client_info.browser,
            os=client_info.os,
        )

    return RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)


# ── Detail ─────────────────────────────────────────────────────────────────────

@router.get(
    "/{short_code}",
    response_model=APIResponse[URLResponse],
    summary="Get URL detail",
    description="Returns full metadata for a short URL by its short code slug.",
    responses={
        200: {"description": "URL metadata returned."},
        404: {"model": ErrorResponse, "description": "Short URL not found or inactive."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def get_url_detail(
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code slug."),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[URLResponse]:
    """GET /api/v1/urls/{short_code} – retrieve URL metadata."""
    url = await svc.get_url_detail(short_code)
    return APIResponse(data=url)


# ── Update ─────────────────────────────────────────────────────────────────────

@router.patch(
    "/{short_code}",
    response_model=APIResponse[URLResponse],
    summary="Update URL",
    description="Modify destination URL, title, description, or expiry. Automatically evicts Redis cache.",
    responses={
        200: {"description": "URL updated successfully."},
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Permission denied (not the owner)."},
        404: {"model": ErrorResponse, "description": "Short URL not found."},
        422: {"model": ErrorResponse, "description": "Validation error in update payload."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def update_url(
    payload: URLUpdateRequest,
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code slug."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> APIResponse[URLResponse]:
    """PATCH /api/v1/urls/{short_code} – update URL metadata."""
    url = await svc.update_url(short_code, payload, owner_id=current_user.id)
    return APIResponse(data=url, message="URL updated successfully.")


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete(
    "/{short_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete URL",
    description="Soft-delete a shortened URL and immediately purge it from the Redis cache.",
    responses={
        204: {"description": "URL deactivated and evicted from cache."},
        401: {"model": ErrorResponse, "description": "Authentication required."},
        403: {"model": ErrorResponse, "description": "Permission denied (not the owner)."},
        404: {"model": ErrorResponse, "description": "Short URL not found."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def delete_url(
    short_code: str = Path(..., min_length=4, max_length=50, description="Short code slug."),
    current_user: User = Depends(get_current_active_user),
    svc: URLService = Depends(get_url_service),
) -> None:
    """DELETE /api/v1/urls/{short_code} – soft delete URL."""
    await svc.delete_url(short_code, owner_id=current_user.id)
