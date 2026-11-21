from typing import Any, Self

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from src.application.ports import UnitOfWork, UnitOfWorkFactory
from src.core.exceptions import ConflictError
from src.infrastructure.sqlalchemy_repositories import (
    SqlAlchemyCourseRepository,
    SqlAlchemyIdempotencyRepository,
    SqlAlchemyOutboxRepository,
    SqlAlchemyRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session = session_factory()
        self.repository = SqlAlchemyRepository(self.session)
        self.courses = SqlAlchemyCourseRepository(self.session)
        self.idempotency = SqlAlchemyIdempotencyRepository(self.session)
        self.outbox = SqlAlchemyOutboxRepository(self.session)
        self._closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self.close()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except StaleDataError as exc:
            await self.session.rollback()
            raise ConflictError("Данные изменены другим запросом") from exc
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("Нарушено ограничение целостности данных") from exc
        except SQLAlchemyError:
            await self.session.rollback()
            raise

    async def rollback(self) -> None:
        await self.session.rollback()

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self.session.close()


class SqlAlchemyUnitOfWorkFactory(UnitOfWorkFactory):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def create(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)
