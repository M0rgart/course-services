import hashlib
import json
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.application.ports import Repository
from src.core import models
from src.core.exceptions import (
    CourseNotFoundError,
    ForbiddenError,
    IdempotencyConflictError,
    SubmissionNotFoundError,
)
from src.web.schemas import (
    Pagination,
    ServiceInfo,
)


def get_service_info() -> ServiceInfo:
    return ServiceInfo()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _scoped_idempotency_key(key: str, operation: str, actor_id: UUID) -> str:
    return _hash(f"{operation}:{actor_id}:{key}")


async def _check_idempotency(
    repository: Repository,
    key: str,
    payload: str,
    operation: str,
    actor_id: UUID,
) -> dict[str, Any] | None:
    scoped_key = _scoped_idempotency_key(key, operation, actor_id)
    claim = (
        sqlite_insert(models.IdempotencyRecord)
        .values(
            key=scoped_key,
            payload_hash=_hash(payload),
            response_json="{}",
        )
        .on_conflict_do_nothing(index_elements=[models.IdempotencyRecord.key])
        .returning(models.IdempotencyRecord.key)
    )
    claimed_key = (await repository.execute(claim)).scalar_one_or_none()
    if claimed_key is not None:
        return None
    record = await repository.get(models.IdempotencyRecord, scoped_key)
    if record is None:
        return None
    if record.payload_hash != _hash(payload):
        raise IdempotencyConflictError()
    return cast(dict[str, Any], json.loads(record.response_json))


async def _remember_idempotency(
    repository: Repository,
    key: str,
    payload: str,
    response: dict[str, Any],
    operation: str,
    actor_id: UUID,
) -> None:
    await repository.execute(
        update(models.IdempotencyRecord)
        .where(models.IdempotencyRecord.key == _scoped_idempotency_key(key, operation, actor_id))
        .values(response_json=json.dumps(response, default=str))
    )


def _pagination(total: int, offset: int, limit: int) -> Pagination:
    return Pagination(offset=offset, limit=limit, total=total)


async def _course_access(
    repository: Repository, course_id: UUID, actor_id: UUID, role: str
) -> bool:
    if role == "admin":
        return True
    course = await repository.get(models.Course, course_id)
    if course is None:
        return False
    if role == "teacher":
        return course.teacher_id == actor_id
    membership = select(models.CourseStudent.id).where(
        models.CourseStudent.course_id == course_id,
        models.CourseStudent.student_id == actor_id,
    )
    return (await repository.execute(membership)).scalar_one_or_none() is not None


async def _require_course_access(
    repository: Repository, course_id: UUID, actor_id: UUID, role: str
) -> None:
    if await _course_access(repository, course_id, actor_id, role):
        return
    if await repository.get(models.Course, course_id) is None:
        raise CourseNotFoundError()
    raise ForbiddenError()


async def _require_assignment_access(
    repository: Repository, assignment: models.Assignment, actor_id: UUID, role: str
) -> None:
    await _require_course_access(repository, assignment.course_id, actor_id, role)


async def _get_submission(
    repository: Repository, submission_id: UUID
) -> tuple[models.Submission, models.Course]:
    submission = await repository.get(models.Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError()
    assignment = await repository.get(models.Assignment, submission.assignment_id)
    if assignment is None:
        raise SubmissionNotFoundError()
    course = await repository.get(models.Course, assignment.course_id)
    if course is None:
        raise SubmissionNotFoundError()
    return submission, course


async def _require_submission_access(
    submission: models.Submission,
    course: models.Course,
    actor_id: UUID,
    role: str,
) -> None:
    if role == "admin":
        return
    if role == "student" and submission.student_id == actor_id:
        return
    if role == "teacher" and course.teacher_id == actor_id:
        return
    raise ForbiddenError()
