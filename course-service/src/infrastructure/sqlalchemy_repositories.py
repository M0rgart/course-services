import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Executable

from src.application.ports import (
    CourseRepository,
    IdempotencyRepository,
    OutboxMessage,
    OutboxRepository,
    Repository,
)
from src.core import models
from src.core.exceptions import IdempotencyConflictError

EntityT = TypeVar("EntityT")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _idempotency_storage_key(key: str, operation: str, actor_id: UUID) -> str:
    return _hash(f"{operation}:{actor_id}:{key}")


class SqlAlchemyRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, entity_type: type[EntityT], entity_id: Any) -> EntityT | None:
        return cast(EntityT | None, await self._session.get(entity_type, entity_id))

    async def execute(self, statement: Executable) -> Result[Any]:
        return await self._session.execute(statement)

    def add(self, entity: Any) -> None:
        self._session.add(entity)

    async def delete(self, entity: Any) -> None:
        await self._session.delete(entity)

    async def flush(self) -> None:
        await self._session.flush()


class SqlAlchemyCourseRepository(CourseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, course: models.Course) -> None:
        self._session.add(course)

    async def flush(self) -> None:
        await self._session.flush()

    async def list_with_assignments(self, offset: int, limit: int) -> list[models.Course]:
        statement = (
            select(models.Course)
            .options(selectinload(models.Course.assignments))
            .order_by(models.Course.created_at)
            .offset(offset)
            .limit(limit)
        )
        return list((await self._session.execute(statement)).scalars().all())

    async def get_with_assignments(self, course_id: UUID) -> models.Course | None:
        statement = (
            select(models.Course)
            .where(models.Course.id == course_id)
            .options(selectinload(models.Course.assignments))
        )
        return (await self._session.execute(statement)).scalar_one_or_none()


class SqlAlchemyIdempotencyRepository(IdempotencyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self, key: str, payload: str, operation: str, actor_id: UUID
    ) -> dict[str, Any] | None:
        storage_key = _idempotency_storage_key(key, operation, actor_id)
        insert = (
            sqlite_insert(models.IdempotencyRecord)
            .values(key=storage_key, payload_hash=_hash(payload), response_json="{}")
            .on_conflict_do_nothing(index_elements=[models.IdempotencyRecord.key])
            .returning(models.IdempotencyRecord.key)
        )
        claimed = (await self._session.execute(insert)).scalar_one_or_none()
        if claimed is not None:
            return None
        record = await self._session.get(models.IdempotencyRecord, storage_key)
        if record is None:
            return None
        if record.payload_hash != _hash(payload):
            raise IdempotencyConflictError()
        return cast(dict[str, Any], json.loads(record.response_json))

    async def remember(
        self,
        key: str,
        payload: str,
        response: dict[str, Any],
        operation: str,
        actor_id: UUID,
    ) -> None:
        await self._session.execute(
            update(models.IdempotencyRecord)
            .where(
                models.IdempotencyRecord.key == _idempotency_storage_key(key, operation, actor_id)
            )
            .values(response_json=json.dumps(response, default=str))
        )


class SqlAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: models.OutboxEvent) -> None:
        self._session.add(event)

    async def claim_next(self) -> OutboxMessage | None:
        now = datetime.now(UTC)
        stale_before = now - timedelta(minutes=1)
        available = or_(
            models.OutboxEvent.status == "PENDING",
            and_(
                models.OutboxEvent.status == "PROCESSING",
                models.OutboxEvent.claimed_at < stale_before,
            ),
        )
        candidate_id = (
            await self._session.execute(
                select(models.OutboxEvent.id)
                .where(available)
                .order_by(models.OutboxEvent.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        if candidate_id is None:
            return None
        claim = (
            update(models.OutboxEvent)
            .where(
                models.OutboxEvent.id == candidate_id,
                available,
            )
            .values(
                status="PROCESSING",
                attempts=models.OutboxEvent.attempts + 1,
                claimed_at=now,
            )
            .returning(
                models.OutboxEvent.id,
                models.OutboxEvent.event_type,
                models.OutboxEvent.payload_json,
            )
        )
        row = (await self._session.execute(claim)).one_or_none()
        if row is None:
            return None
        payload = json.loads(row.payload_json)
        return OutboxMessage(
            id=row.id,
            event_type=row.event_type,
            payload=cast(dict[str, Any], payload),
        )

    async def mark_completed(self, event_id: UUID) -> None:
        await self._session.execute(
            update(models.OutboxEvent)
            .where(models.OutboxEvent.id == event_id)
            .values(
                status="COMPLETED",
                processed_at=datetime.now(UTC),
                claimed_at=None,
                last_error=None,
            )
        )

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        await self._session.execute(
            update(models.OutboxEvent)
            .where(models.OutboxEvent.id == event_id)
            .values(status="PENDING", claimed_at=None, last_error=error[:1024])
        )
