from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Protocol, Self, TypeVar
from uuid import UUID

from sqlalchemy.engine import Result
from sqlalchemy.sql import Executable

from src.core.models import Course, OutboxEvent

EntityT = TypeVar("EntityT")


class Repository(Protocol):
    async def get(self, entity_type: type[EntityT], entity_id: Any) -> EntityT | None: ...

    async def execute(self, statement: Executable) -> Result[Any]: ...

    def add(self, entity: Any) -> None: ...

    async def delete(self, entity: Any) -> None: ...

    async def flush(self) -> None: ...


@dataclass(frozen=True)
class OutboxMessage:
    id: UUID
    event_type: str
    payload: dict[str, Any]


class CourseRepository(Protocol):
    async def add(self, course: Course) -> None: ...

    async def flush(self) -> None: ...

    async def list_with_assignments(self, offset: int, limit: int) -> list[Course]: ...

    async def get_with_assignments(self, course_id: UUID) -> Course | None: ...


class IdempotencyRepository(Protocol):
    async def claim(
        self, key: str, payload: str, operation: str, actor_id: UUID
    ) -> dict[str, Any] | None: ...

    async def remember(
        self,
        key: str,
        payload: str,
        response: dict[str, Any],
        operation: str,
        actor_id: UUID,
    ) -> None: ...


class OutboxRepository(Protocol):
    async def add(self, event: OutboxEvent) -> None: ...

    async def claim_next(self) -> OutboxMessage | None: ...

    async def mark_completed(self, event_id: UUID) -> None: ...

    async def mark_failed(self, event_id: UUID, error: str) -> None: ...


class UnitOfWork(Protocol):
    repository: Repository
    courses: CourseRepository
    idempotency: IdempotencyRepository
    outbox: OutboxRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def close(self) -> None: ...

    async def __aenter__(self) -> Self: ...

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None: ...


class EventPublisher(Protocol):
    def publish(self, message: OutboxMessage) -> Awaitable[None]: ...


class UnitOfWorkFactory(Protocol):
    def create(self) -> UnitOfWork: ...
