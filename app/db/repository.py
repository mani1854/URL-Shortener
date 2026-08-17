"""
db/repository.py

Generic async repository (base class).
Concrete repositories in app/services/ extend this to gain
standard CRUD operations without repeating boilerplate.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Async generic CRUD repository.

    Subclass this for each SQLAlchemy model:

        class URLRepository(BaseRepository[URL]):
            model = URL
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, pk: Any) -> ModelT | None:
        """Fetch a single record by primary key."""
        return await self.session.get(self.model, pk)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        """Return a page of records."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return result.scalars().all()

    async def create(self, **kwargs: Any) -> ModelT:
        """Persist a new record and return it."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()   # populate server-generated defaults
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """Apply keyword updates to an existing record."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Remove a record from the database."""
        await self.session.delete(instance)
        await self.session.flush()
