from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import Depends, Request
from sqlalchemy import DateTime, TypeDecorator, event
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import Settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.db.url,
            echo=settings.db.echo,
            pool_pre_ping=True,
        )
        if settings.db.url.startswith("sqlite"):

            @event.listens_for(self.engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn: Any, _connection_record: Any) -> None:
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_uow(request: Request) -> AsyncIterator[Any]:
    unit_of_work_factory = cast(Any, request.app.state.uow_factory)
    async with unit_of_work_factory.create() as unit_of_work:
        yield unit_of_work


async def get_repository(
    unit_of_work: Annotated[Any, Depends(get_uow)],
) -> AsyncIterator[Any]:
    yield unit_of_work.repository
