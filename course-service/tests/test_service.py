import json
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID, uuid4

import pytest
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.sql import Executable

from src.application.create_course import CreateCourseUseCase
from src.application.ports import (
    CourseRepository,
    EventPublisher,
    IdempotencyRepository,
    OutboxMessage,
    OutboxRepository,
    Repository,
    UnitOfWork,
)
from src.core.db import Base
from src.core.exceptions import IdempotencyConflictError
from src.core.models import Course, OutboxEvent
from src.infrastructure.outbox import OutboxDispatcher, OutboxPublishError
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWorkFactory
from src.web.schemas import CourseCreate


class FakeCourseRepository(CourseRepository):
    def __init__(self) -> None:
        self.courses: list[Course] = []

    async def add(self, course: Course) -> None:
        now = datetime.now(UTC)
        course.id = uuid4()
        course.created_at = now
        course.updated_at = now
        self.courses.append(course)

    async def flush(self) -> None:
        return None

    async def list_with_assignments(self, offset: int, limit: int) -> list[Course]:
        return self.courses[offset : offset + limit]

    async def get_with_assignments(self, course_id: UUID) -> Course | None:
        return next((course for course in self.courses if course.id == course_id), None)


class FakeIdempotencyRepository(IdempotencyRepository):
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, UUID], tuple[str, dict[str, Any] | None]] = {}

    async def claim(
        self, key: str, payload: str, operation: str, actor_id: UUID
    ) -> dict[str, Any] | None:
        scoped_key = (key, operation, actor_id)
        record = self.records.get(scoped_key)
        if record is None:
            self.records[scoped_key] = (payload, None)
            return None
        if record[0] != payload:
            raise IdempotencyConflictError()
        return record[1]

    async def remember(
        self,
        key: str,
        payload: str,
        response: dict[str, Any],
        operation: str,
        actor_id: UUID,
    ) -> None:
        self.records[(key, operation, actor_id)] = (payload, response)


class FakeRepository(Repository):
    async def get(self, entity_type: type[Any], entity_id: Any) -> Any | None:
        return None

    async def execute(self, statement: Executable) -> Result[Any]:
        raise NotImplementedError

    def add(self, entity: Any) -> None:
        return None

    async def delete(self, entity: Any) -> None:
        return None

    async def flush(self) -> None:
        return None


class FakeOutboxRepository(OutboxRepository):
    async def add(self, event: OutboxEvent) -> None:
        return None

    async def claim_next(self) -> OutboxMessage | None:
        return None

    async def mark_completed(self, event_id: UUID) -> None:
        return None

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        return None


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.repository = FakeRepository()
        self.courses = FakeCourseRepository()
        self.idempotency = FakeIdempotencyRepository()
        self.outbox = FakeOutboxRepository()

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_create_course_use_case_uses_only_ports() -> None:
    unit_of_work = FakeUnitOfWork()
    use_case = CreateCourseUseCase(unit_of_work)
    actor_id = uuid4()
    payload = CourseCreate(
        title="A sufficiently long course title",
        teacher_id=uuid4(),
    )

    created = await use_case.execute("idempotency-key", payload, actor_id)
    replay = await use_case.execute("idempotency-key", payload, actor_id)

    assert created.id == replay.id
    assert len(unit_of_work.courses.courses) == 1


class FlakyPublisher(EventPublisher):
    def __init__(self) -> None:
        self.calls = 0
        self.delivered: list[UUID] = []

    async def publish(self, message: OutboxMessage) -> None:
        self.calls += 1
        if self.calls == 1:
            raise OutboxPublishError("temporary delivery failure")
        self.delivered.append(message.id)


@pytest.mark.asyncio
async def test_transactional_outbox_retries_and_marks_delivery(tmp_path) -> None:
    database_path = (tmp_path / "outbox.db").as_posix()
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    unit_of_work_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
    publisher = FlakyPublisher()
    dispatcher = OutboxDispatcher(unit_of_work_factory, publisher, polling_interval=0.01)
    event_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with unit_of_work_factory.create() as unit_of_work:
            await unit_of_work.outbox.add(
                OutboxEvent(
                    id=event_id,
                    event_type="submission.created",
                    payload_json=json.dumps({"submission_id": str(uuid4())}),
                )
            )

        assert await dispatcher.dispatch_once()
        async with unit_of_work_factory.create() as unit_of_work:
            event = await unit_of_work.repository.get(OutboxEvent, event_id)
            assert event is not None
            assert event.status == "PENDING"
            assert event.attempts == 1

        assert await dispatcher.dispatch_once()
        async with unit_of_work_factory.create() as unit_of_work:
            event = await unit_of_work.repository.get(OutboxEvent, event_id)
            assert event is not None
            assert event.status == "COMPLETED"
            assert event.processed_at is not None
        assert publisher.delivered == [event_id]
    finally:
        await engine.dispose()
