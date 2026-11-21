import json
from datetime import date
from uuid import UUID

from pydantic import AnyUrl, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.application.common import (
    _check_idempotency,
    _get_submission,
    _pagination,
    _remember_idempotency,
    _require_submission_access,
)
from src.application.ports import OutboxRepository, Repository
from src.core import models
from src.core.exceptions import (
    AssignmentNotFoundError,
    ForbiddenError,
    RateLimitError,
    ValidationError,
)
from src.web.schemas import (
    Artifact,
    Artifacts,
    Submission,
    SubmissionCreate,
    Submissions,
)


async def list_submissions(
    repository: Repository,
    offset: int,
    limit: int,
    assignment_id: UUID | None,
    actor_id: UUID,
    role: str,
) -> Submissions:
    stmt = (
        select(models.Submission)
        .join(models.Assignment, models.Assignment.id == models.Submission.assignment_id)
        .join(models.Course, models.Course.id == models.Assignment.course_id)
    )
    if assignment_id is not None:
        stmt = stmt.where(models.Submission.assignment_id == assignment_id)
    if role == "student":
        stmt = stmt.where(models.Submission.student_id == actor_id)
    elif role == "teacher":
        stmt = stmt.where(models.Course.teacher_id == actor_id)
    total = (
        await repository.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await repository.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Submissions(
        data=[Submission.model_validate(submission) for submission in rows],
        pagination=_pagination(total, offset, limit),
    )


async def create_submission(
    repository: Repository,
    key: str,
    payload: SubmissionCreate,
    actor_id: UUID,
    outbox: OutboxRepository,
) -> Submission:
    assignment = await repository.get(models.Assignment, payload.assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    course = await repository.get(models.Course, assignment.course_id)
    if course is None:
        raise AssignmentNotFoundError()
    membership = select(models.CourseStudent.id).where(
        models.CourseStudent.course_id == course.id,
        models.CourseStudent.student_id == actor_id,
    )
    if (await repository.execute(membership)).scalar_one_or_none() is None:
        raise ForbiddenError()
    today = date.today()
    if today < assignment.date_start or today > assignment.date_end:
        raise ValidationError("Срок отправки задания не активен")
    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(repository, key, payload_json, "create_submission", actor_id)
    if cached is not None:
        return Submission.model_validate(cached)
    existing = (
        await repository.execute(
            select(func.count())
            .select_from(models.Submission)
            .where(
                models.Submission.assignment_id == payload.assignment_id,
                models.Submission.student_id == actor_id,
            )
        )
    ).scalar_one()
    counter = models.SubmissionAttemptCounter
    stmt = (
        sqlite_insert(counter)
        .values(
            assignment_id=payload.assignment_id,
            student_id=actor_id,
            attempt_count=existing + 1,
        )
        .on_conflict_do_update(
            index_elements=[counter.assignment_id, counter.student_id],
            set_={"attempt_count": counter.attempt_count + 1},
            where=counter.attempt_count < assignment.submit_limit,
        )
        .returning(counter.attempt_count)
    )
    reserved_attempt = (await repository.execute(stmt)).scalar_one_or_none()
    if reserved_attempt is None or reserved_attempt > assignment.submit_limit:
        raise RateLimitError()
    submission = models.Submission(
        assignment_id=payload.assignment_id,
        student_id=actor_id,
        repository_url=str(payload.repository_url) if payload.repository_url else None,
        artifacts_url=str(payload.artifacts_url) if payload.artifacts_url else None,
    )
    repository.add(submission)
    await repository.flush()
    result = Submission.model_validate(submission)
    await outbox.add(
        models.OutboxEvent(
            event_type="submission.created",
            payload_json=json.dumps(
                {
                    "submission_id": str(submission.id),
                    "assignment_id": str(submission.assignment_id),
                    "student_id": str(submission.student_id),
                }
            ),
        )
    )
    await _remember_idempotency(
        repository, key, payload_json, result.model_dump(), "create_submission", actor_id
    )
    return result


async def get_submission(
    repository: Repository, submission_id: UUID, actor_id: UUID, role: str
) -> Submission:
    submission, course = await _get_submission(repository, submission_id)
    await _require_submission_access(submission, course, actor_id, role)
    return Submission.model_validate(submission)


async def get_submission_artifacts(
    repository: Repository, submission_id: UUID, actor_id: UUID, role: str
) -> Artifacts:
    submission, course = await _get_submission(repository, submission_id)
    await _require_submission_access(submission, course, actor_id, role)
    if submission.artifacts_url is None:
        return Artifacts(data=[])
    return Artifacts(
        data=[
            Artifact(
                id=submission.id,
                submission_id=submission.id,
                url=TypeAdapter(AnyUrl).validate_python(submission.artifacts_url),
                type="file",
            )
        ]
    )
