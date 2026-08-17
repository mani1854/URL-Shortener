"""
services/url_service.py

Business-logic layer for URL shortening and URL management operations.

Architecture:
  - URLRepository handles direct database queries via AsyncSession.
  - URLService coordinates validation, short code generation, persistence,
    cache-aside reads/writes, and response mapping.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AliasAlreadyExistsError,
    AppException,
    InvalidURLError,
    PermissionDeniedError,
    ShortURLNotFoundError,
    URLExpiredError,
)
from app.db.repository import BaseRepository
from app.models.url import URL
from app.schemas.dashboard import PaginatedUserURLsResponse, UserURLItem
from app.schemas.url import (
    URLCreateRequest,
    URLListResponse,
    URLResponse,
    URLUpdateRequest,
)
from app.utils.cache import CacheClient
from app.utils.shortcode import (
    generate_base62_code,
    is_valid_custom_alias,
)

logger = logging.getLogger(__name__)

MAX_COLLISION_RETRIES = 5


class URLRepository(BaseRepository[URL]):
    """Concrete repository for URL CRUD operations."""

    model = URL

    async def get_by_short_code(self, short_code: str) -> URL | None:
        """Fetch a single URL by its unique short_code."""
        result = await self.session.execute(
            select(URL).where(URL.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def short_code_exists(self, short_code: str) -> bool:
        """Check whether short_code is already registered in the database."""
        result = await self.session.execute(
            select(func.count()).select_from(URL).where(URL.short_code == short_code)
        )
        return (result.scalar() or 0) > 0

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        active_only: bool = True,
    ) -> tuple[Sequence[URL], int]:
        """
        Return paginated list of URLs owned by *owner_id* alongside total count.
        """
        base_query = select(URL).where(URL.user_id == owner_id)
        count_query = select(func.count()).select_from(URL).where(URL.user_id == owner_id)

        if active_only:
            base_query = base_query.where(URL.is_active.is_(True))
            count_query = count_query.where(URL.is_active.is_(True))

        total = (await self.session.execute(count_query)).scalar() or 0

        paginated_query = (
            base_query.order_by(URL.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(paginated_query)
        return result.scalars().all(), total

    async def increment_click_count(self, url_id: uuid.UUID) -> None:
        """Atomically increment the denormalized click_count column."""
        await self.session.execute(
            update(URL)
            .where(URL.id == url_id)
            .values(click_count=URL.click_count + 1)
        )
        await self.session.flush()


class URLService:
    """
    High-level URL shortening operations.
    """

    def __init__(self, db: AsyncSession, cache: CacheClient) -> None:
        self.repo = URLRepository(db)
        self.cache = cache

    def _build_short_url(self, short_code: str) -> str:
        """Construct fully qualified short URL."""
        base = str(settings.BASE_URL).rstrip("/")
        return f"{base}/{short_code}"

    def _to_response(self, record: URL) -> URLResponse:
        """Convert ORM model to Pydantic URLResponse schema."""
        now = datetime.now(UTC)
        return URLResponse(
            id=record.id,
            original_url=record.original_url,
            short_code=record.short_code,
            short_url=self._build_short_url(record.short_code),
            user_id=record.user_id,
            title=getattr(record, "title", None),
            description=getattr(record, "description", None),
            is_active=getattr(record, "is_active", True) if getattr(record, "is_active", None) is not None else True,
            is_custom=getattr(record, "is_custom", False) if getattr(record, "is_custom", None) is not None else False,
            click_count=getattr(record, "click_count", 0) or 0,
            expires_at=getattr(record, "expires_at", None),
            created_at=getattr(record, "created_at", None) or now,
            updated_at=getattr(record, "updated_at", None) or now,
        )

    def _to_dashboard_item(self, record: URL) -> UserURLItem:
        """Convert ORM model to dashboard UserURLItem schema."""
        now = datetime.now(UTC)
        return UserURLItem(
            id=record.id,
            original_url=record.original_url,
            short_url=self._build_short_url(record.short_code),
            short_code=record.short_code,
            clicks=getattr(record, "click_count", 0) or 0,
            expiry=getattr(record, "expires_at", None),
            created_date=getattr(record, "created_at", None) or now,
            title=getattr(record, "title", None),
            is_active=getattr(record, "is_active", True) if getattr(record, "is_active", None) is not None else True,
            is_custom=getattr(record, "is_custom", False) if getattr(record, "is_custom", None) is not None else False,
        )

    # ── Create ─────────────────────────────────────────────────────────────────

    async def create_short_url(
        self,
        payload: URLCreateRequest,
        *,
        owner_id: uuid.UUID | str | None = None,
    ) -> URLResponse:
        """
        Validate input, generate Base62 code or check custom alias, persist,
        optionally pre-warm cache, and return response.

        Raises:
            InvalidURLError: If URL or alias format is invalid.
            AliasAlreadyExistsError: If requested custom alias is taken.
        """
        # Validate owner_id if passed as string
        user_uuid: uuid.UUID | None = None
        if owner_id is not None:
            if isinstance(owner_id, str):
                try:
                    user_uuid = uuid.UUID(owner_id)
                except ValueError:
                    user_uuid = None
            else:
                user_uuid = owner_id

        # Determine short_code
        if payload.custom_alias:
            alias = payload.custom_alias.strip()
            if not is_valid_custom_alias(alias):
                raise InvalidURLError(
                    detail="Invalid custom alias. Must be 4-50 chars [a-zA-Z0-9_-] and not reserved."
                )

            if await self.repo.short_code_exists(alias):
                raise AliasAlreadyExistsError()

            short_code = alias
            is_custom = True
        else:
            # Generate random unique Base62 code with collision retry loop
            short_code = None
            for _ in range(MAX_COLLISION_RETRIES):
                candidate = generate_base62_code(length=settings.SHORT_CODE_LENGTH)
                if not await self.repo.short_code_exists(candidate):
                    short_code = candidate
                    break

            if short_code is None:
                logger.error("Failed to generate unique short code after %d attempts", MAX_COLLISION_RETRIES)
                raise AppException(detail="Could not generate unique short code. Please try again.")

            is_custom = False

        # Create record in DB
        url_record = await self.repo.create(
            original_url=str(payload.original_url),
            short_code=short_code,
            user_id=user_uuid,
            title=payload.title,
            description=payload.description,
            expires_at=payload.expires_at,
            is_custom=is_custom,
        )

        # Pre-warm Redis cache (graceful fallback if Redis is down)
        try:
            await self.cache.set_original_url(short_code, str(payload.original_url))
        except Exception as exc:
            logger.warning("Failed to pre-warm cache for %s: %s", short_code, exc)

        logger.info("Created short URL %s -> %s (owner=%s)", short_code, payload.original_url, user_uuid)
        return self._to_response(url_record)

    # ── Read ───────────────────────────────────────────────────────────────────

    async def resolve_short_code(self, short_code: str) -> str:
        """
        Return the original URL for a short code with cache-first lookup.

        Raises:
            ShortURLNotFoundError: If short code does not exist or is inactive.
            URLExpiredError: If link has expired.
        """
        # 1. Try Redis cache
        try:
            cached_url = await self.cache.get_original_url(short_code)
            if cached_url:
                return cached_url
        except Exception as exc:
            logger.debug("Redis cache check error for %s: %s", short_code, exc)

        # 2. Query PostgreSQL
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()

        # Check expiry
        if record.expires_at is not None:
            now_utc = datetime.now(UTC)
            compare_exp = (
                record.expires_at
                if record.expires_at.tzinfo is not None
                else record.expires_at.replace(tzinfo=UTC)
            )
            if compare_exp <= now_utc:
                raise URLExpiredError()

        # 3. Populate Redis cache for next time
        try:
            await self.cache.set_original_url(short_code, record.original_url)
        except Exception as exc:
            logger.warning("Failed to set cache for %s: %s", short_code, exc)

        return record.original_url

    async def get_url_detail(self, short_code: str) -> URLResponse:
        """Fetch full URL metadata."""
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()
        return self._to_response(record)

    async def list_urls(
        self,
        owner_id: uuid.UUID | str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> URLListResponse:
        """Paginated list of URLs owned by user."""
        user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
        offset = (page - 1) * page_size

        records, total = await self.repo.list_by_owner(
            user_uuid, limit=page_size, offset=offset, active_only=True
        )

        items = [self._to_response(r) for r in records]
        has_next = (offset + page_size) < total

        return URLListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
        )

    async def list_dashboard_urls(
        self,
        owner_id: uuid.UUID | str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedUserURLsResponse:
        """
        Return a paginated list of URLs owned by the user formatted for dashboard views.
        """
        import math
        user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
        offset = (page - 1) * page_size

        records, total = await self.repo.list_by_owner(
            user_uuid, limit=page_size, offset=offset, active_only=True
        )

        items = [self._to_dashboard_item(r) for r in records]
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        has_next = (offset + page_size) < total
        has_prev = page > 1

        return PaginatedUserURLsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

    # ── Update ─────────────────────────────────────────────────────────────────

    async def update_url(
        self,
        short_code: str,
        payload: URLUpdateRequest,
        *,
        owner_id: uuid.UUID | str | None = None,
    ) -> URLResponse:
        """
        Update mutable fields on an existing short URL and evict cache.
        """
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()

        # Check ownership if specified
        if owner_id is not None:
            user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
            if record.user_id != user_uuid:
                raise PermissionDeniedError()

        updates = {}
        if payload.original_url is not None:
            updates["original_url"] = str(payload.original_url)
        if payload.title is not None:
            updates["title"] = payload.title
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.expires_at is not None:
            updates["expires_at"] = payload.expires_at
        if payload.is_active is not None:
            updates["is_active"] = payload.is_active

        updated_record = await self.repo.update(record, **updates)

        # Evict cache on modification
        try:
            await self.cache.evict_short_code(short_code)
        except Exception as exc:
            logger.warning("Failed to evict cache for %s: %s", short_code, exc)

        return self._to_response(updated_record)

    async def update_url_expiry(
        self,
        short_code: str,
        new_expiry: datetime | None,
        *,
        owner_id: uuid.UUID | str,
    ) -> UserURLItem:
        """
        Update or clear the expiry date on a user's short URL and evict cache.
        """
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()

        user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
        if record.user_id != user_uuid:
            raise PermissionDeniedError()

        updated_record = await self.repo.update(record, expires_at=new_expiry)

        # Evict cache on expiry update
        try:
            await self.cache.evict_short_code(short_code)
        except Exception as exc:
            logger.warning("Failed to evict cache for %s on expiry update: %s", short_code, exc)

        return self._to_dashboard_item(updated_record)

    # ── Delete ─────────────────────────────────────────────────────────────────

    async def delete_url(
        self,
        short_code: str,
        *,
        owner_id: uuid.UUID | str | None = None,
    ) -> None:
        """
        Soft-delete a short URL and evict from cache.
        """
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            raise ShortURLNotFoundError()

        if owner_id is not None:
            user_uuid = uuid.UUID(str(owner_id)) if not isinstance(owner_id, uuid.UUID) else owner_id
            if record.user_id != user_uuid:
                raise PermissionDeniedError()

        # Soft delete
        await self.repo.update(record, is_active=False)

        # Evict from cache
        try:
            await self.cache.evict_short_code(short_code)
        except Exception as exc:
            logger.warning("Failed to evict cache for %s on delete: %s", short_code, exc)

    # ── Analytics ──────────────────────────────────────────────────────────────

    async def record_click(self, short_code: str) -> None:
        """Increment click count on URL record."""
        record = await self.repo.get_by_short_code(short_code)
        if record is not None:
            await self.repo.increment_click_count(record.id)

    async def record_click_analytics(
        self,
        short_code: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
        referer: str | None = None,
        device_type: str | None = None,
        browser: str | None = None,
        os: str | None = None,
        country: str | None = None,
    ) -> None:
        """
        Record detailed click analytics and increment click count.
        """
        record = await self.repo.get_by_short_code(short_code)
        if record is None or not record.is_active:
            return

        # 1. Atomically increment counter on URL
        await self.repo.increment_click_count(record.id)

        # 2. Insert ClickAnalytics entry
        from app.models.click_analytics import ClickAnalytics
        analytics_entry = ClickAnalytics(
            url_id=record.id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            device_type=device_type,
            browser=browser,
            os=os,
            country=country,
        )
        self.repo.session.add(analytics_entry)
        await self.repo.session.flush()


async def record_background_click(
    short_code: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
    referer: str | None = None,
    device_type: str | None = None,
    browser: str | None = None,
    os: str | None = None,
    country: str | None = None,
) -> None:
    """
    Standalone background task function that creates an isolated session
    to persist click analytics and update counters without blocking responses.
    """
    from app.db.session import get_session_factory
    from app.utils.geoip import lookup_ip_geolocation
    try:
        # GeoIP lookup
        geo_country = country
        geo_city = None
        if not geo_country and ip_address:
            try:
                geo_country, geo_city = await lookup_ip_geolocation(ip_address)
            except Exception as geo_exc:
                logger.debug("GeoIP error for %s: %s", ip_address, geo_exc)

        factory = get_session_factory()
        async with factory() as session:
            repo = URLRepository(session)
            record = await repo.get_by_short_code(short_code)
            if record is None or not record.is_active:
                return

            await repo.increment_click_count(record.id)

            from app.models.click_analytics import ClickAnalytics
            analytics_entry = ClickAnalytics(
                url_id=record.id,
                ip_address=ip_address,
                user_agent=user_agent,
                referer=referer,
                device_type=device_type,
                browser=browser,
                os=os,
                country=geo_country,
                city=geo_city,
            )
            session.add(analytics_entry)
            await session.commit()
            logger.debug("Background click recorded for %s from IP %s (country=%s)", short_code, ip_address, geo_country)
    except Exception as exc:
        logger.warning("Failed to record background click analytics for %s: %s", short_code, exc)
