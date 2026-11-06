import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import models
from src.core.exceptions import (
    AssignmentNotFoundError,
    ConflictError,
    CourseNotFoundError,
    ForbiddenError,
    RateLimitError,
    ReviewNotFoundError,
    SubmissionNotFoundError,
    ValidationError,
)
from src.core.external import AsyncExternalService, ExternalServiceError
from src.web.schemas import (
    Artifact,
    Artifacts,
    Assignment,
    AssignmentCreate,
    Assignments,
    AssignmentUpdate,
    Course,
    CourseCreate,
    Courses,
    CourseStudents,
    CourseUpdate,
    Pagination,
    Review,
    ReviewCreate,
    ReviewUpdate,
    ServiceInfo,
    Status1,
    Submission,
    SubmissionCreate,
    Submissions,
)

logger = logging.getLogger(__name__)


def get_service_info() -> ServiceInfo:
    return ServiceInfo()


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


async def _check_idempotency(
    session: AsyncSession, key: str, payload: str
) -> dict[str, Any] | None:
    stmt = select(models.IdempotencyRecord).where(models.IdempotencyRecord.key == key)
    record = (await session.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    if record.payload_hash != _hash(payload):
        raise ConflictError("Idempotency-Key reuse with different payload")
    return json.loads(record.response_json)


async def _remember_idempotency(
    session: AsyncSession, key: str, payload: str, response: dict[str, Any]
) -> None:
    session.add(
        models.IdempotencyRecord(
            key=key,
            payload_hash=_hash(payload),
            response_json=json.dumps(response, default=str),
        )
    )


def _paginate(total: int, offset: int, limit: int) -> Pagination:
    return Pagination(offset=offset, limit=limit, total=total)


async def list_courses(
    session: AsyncSession,
    offset: int,
    limit: int,
    sort: str | None,
    status: Status1 | None,
) -> Courses:
    stmt = select(models.Course)
    if status is not None:
        stmt = stmt.where(models.Course.status == status.value)

    if sort:
        for raw in sort.split(","):
            field_name, separator, direction = raw.partition(":")
            if separator:
                if direction.lower() not in {"asc", "desc"}:
                    raise ValidationError(f"Unknown sort direction: {direction}")
                desc = direction.lower() == "desc"
            else:
                desc = field_name.startswith("-")
                field_name = field_name.removeprefix("-")
            column = getattr(models.Course, field_name, None)
            if column is None or field_name not in models.Course.__table__.columns:
                raise ValidationError(f"Unknown sort field: {field_name}")
            stmt = stmt.order_by(column.desc() if desc else column.asc())

    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Courses(
        data=[Course.model_validate(c) for c in rows],
        pagination=_paginate(total, offset, limit),
    )


async def create_course(
    session: AsyncSession, key: str, payload: CourseCreate, teacher_id: UUID
) -> Course:
    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(session, key, payload_json)
    if cached is not None:
        return Course.model_validate(cached)

    course = models.Course(
        title=payload.title,
        description=payload.description,
        teacher_id=payload.teacher_id,
        status=models.CourseStatus(payload.status or "DRAFT"),
    )
    session.add(course)
    await session.flush()
    result = Course.model_validate(course)
    await _remember_idempotency(session, key, payload_json, result.model_dump())
    return result


async def get_course(session: AsyncSession, course_id: UUID) -> Course:
    course = await session.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    return Course.model_validate(course)


async def update_course(
    session: AsyncSession, course_id: UUID, payload: CourseUpdate, actor_id: UUID
) -> Course:
    course = await session.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    if course.teacher_id != actor_id:
        raise ForbiddenError()

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await session.flush()
    return Course.model_validate(course)


async def delete_course(session: AsyncSession, course_id: UUID, actor_id: UUID) -> None:
    course = await session.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    if course.teacher_id != actor_id:
        raise ForbiddenError()
    await session.delete(course)
    await session.flush()


async def get_course_students(session: AsyncSession, course_id: UUID) -> CourseStudents:
    if await session.get(models.Course, course_id) is None:
        raise CourseNotFoundError()
    stmt = select(models.CourseStudent.student_id).where(
        models.CourseStudent.course_id == course_id
    )
    ids = list((await session.execute(stmt)).scalars().all())
    return CourseStudents(course_id=course_id, students_ids=ids)


async def enroll_student(
    session: AsyncSession, course_id: UUID, student_id: UUID, actor_id: UUID
) -> None:
    course = await session.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    if course.teacher_id != actor_id:
        raise ForbiddenError()

    stmt = select(models.CourseStudent).where(
        models.CourseStudent.course_id == course_id,
        models.CourseStudent.student_id == student_id,
    )
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise ConflictError("Student already enrolled")
    session.add(models.CourseStudent(course_id=course_id, student_id=student_id))


async def unenroll_student(
    session: AsyncSession, course_id: UUID, student_id: UUID, actor_id: UUID
) -> None:
    course = await session.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    if course.teacher_id != actor_id:
        raise ForbiddenError()

    stmt = select(models.CourseStudent).where(
        models.CourseStudent.course_id == course_id,
        models.CourseStudent.student_id == student_id,
    )
    link = (await session.execute(stmt)).scalar_one_or_none()
    if link is None:
        raise CourseNotFoundError()
    await session.delete(link)


async def list_assignments(
    session: AsyncSession, offset: int, limit: int, course_id: UUID | None
) -> Assignments:
    stmt = select(models.Assignment)
    if course_id is not None:
        stmt = stmt.where(models.Assignment.course_id == course_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Assignments(
        data=[Assignment.model_validate(a) for a in rows],
        pagination=_paginate(total, offset, limit),
    )


async def create_assignment(
    session: AsyncSession, key: str, payload: AssignmentCreate, actor_id: UUID
) -> Assignment:
    course = await session.get(models.Course, payload.course_id)
    if course is None:
        raise CourseNotFoundError()
    if course.teacher_id != actor_id:
        raise ForbiddenError()
    if payload.date_end < payload.date_start:
        raise ValidationError("date_end must be >= date_start")

    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(session, key, payload_json)
    if cached is not None:
        return Assignment.model_validate(cached)

    assignment = models.Assignment(
        title=payload.title,
        description=payload.description,
        course_id=payload.course_id,
        submit_limit=payload.submit_limit,
        date_start=payload.date_start,
        date_end=payload.date_end,
        materials_url=str(payload.materials_url) if payload.materials_url else None,
    )
    session.add(assignment)
    await session.flush()
    result = Assignment.model_validate(assignment)
    await _remember_idempotency(session, key, payload_json, result.model_dump())
    return result


async def get_assignment(session: AsyncSession, assignment_id: UUID) -> Assignment:
    assignment = await session.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    return Assignment.model_validate(assignment)


async def update_assignment(
    session: AsyncSession, assignment_id: UUID, payload: AssignmentUpdate, actor_id: UUID
) -> Assignment:
    assignment = await session.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    course = await session.get(models.Course, assignment.course_id)
    if course is None or course.teacher_id != actor_id:
        raise ForbiddenError()

    updates = payload.model_dump(exclude_unset=True)
    if "materials_url" in updates and updates["materials_url"] is not None:
        updates["materials_url"] = str(updates["materials_url"])
    for field, value in updates.items():
        setattr(assignment, field, value)

    if assignment.date_end < assignment.date_start:
        raise ValidationError("date_end must be >= date_start")
    await session.flush()
    return Assignment.model_validate(assignment)


async def delete_assignment(
    session: AsyncSession, assignment_id: UUID, actor_id: UUID
) -> None:
    assignment = await session.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    course = await session.get(models.Course, assignment.course_id)
    if course is None or course.teacher_id != actor_id:
        raise ForbiddenError()
    await session.delete(assignment)
    await session.flush()


async def list_submissions(
    session: AsyncSession,
    offset: int,
    limit: int,
    assignment_id: UUID | None,
    actor_id: UUID,
) -> Submissions:
    stmt = select(models.Submission)
    if assignment_id is not None:
        stmt = stmt.where(models.Submission.assignment_id == assignment_id)
    stmt = stmt.where(models.Submission.student_id == actor_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Submissions(
        data=[Submission.model_validate(s) for s in rows],
        pagination=_paginate(total, offset, limit),
    )


async def create_submission(
    session: AsyncSession, key: str, payload: SubmissionCreate, actor_id: UUID
) -> Submission:
    assignment = await session.get(models.Assignment, payload.assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()

    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(session, key, payload_json)
    if cached is not None:
        return Submission.model_validate(cached)

    stmt = (
        select(func.count())
        .select_from(models.Submission)
        .where(
            models.Submission.assignment_id == payload.assignment_id,
            models.Submission.student_id == actor_id,
        )
    )
    existing = (await session.execute(stmt)).scalar_one()
    if existing >= assignment.submit_limit:
        raise RateLimitError("Submit limit exceeded")

    submission = models.Submission(
        assignment_id=payload.assignment_id,
        student_id=actor_id,
        repository_url=str(payload.repository_url) if payload.repository_url else None,
        artifacts_url=str(payload.artifacts_url) if payload.artifacts_url else None,
    )
    session.add(submission)
    await session.flush()
    result = Submission.model_validate(submission)
    await _remember_idempotency(session, key, payload_json, result.model_dump())
    return result


async def get_submission(
    session: AsyncSession, submission_id: UUID, actor_id: UUID
) -> Submission:
    submission = await session.get(models.Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError()
    if submission.student_id != actor_id:
        raise ForbiddenError()
    return Submission.model_validate(submission)


async def get_submission_artifacts(
    session: AsyncSession, submission_id: UUID, actor_id: UUID
) -> Artifacts:
    submission = await session.get(models.Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError()
    if submission.student_id != actor_id:
        raise ForbiddenError()
    if submission.artifacts_url is None:
        return Artifacts(data=[])
    return Artifacts(
        data=[
            Artifact(
                id=submission.id,
                submission_id=submission.id,
                url=submission.artifacts_url,
                type="file",
            )
        ]
    )


async def create_review(
    session: AsyncSession,
    key: str,
    submission_id: UUID,
    payload: ReviewCreate,
    actor_id: UUID,
    external_service: AsyncExternalService,
) -> Review:
    submission = await session.get(models.Submission, submission_id)
    if submission is None:
        raise SubmissionNotFoundError()
    assignment = await session.get(models.Assignment, submission.assignment_id)
    course = (
        await session.get(models.Course, assignment.course_id) if assignment is not None else None
    )
    if course is None or course.teacher_id != actor_id:
        raise ForbiddenError()

    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(session, key, payload_json)
    if cached is not None:
        return Review.model_validate(cached)
    if submission.review_id is not None:
        raise ConflictError("Submission already reviewed")

    mark = payload.mark
    auto_score = payload.auto_score
    feedback = payload.feedback
    if payload.type.value == "AUTO":
        external_result = await external_service.evaluate_submission(
            submission_id, submission.assignment_id, payload.mark
        )
        score = external_result.get("auto_score")
        if (
            not isinstance(score, (float, int))
            or isinstance(score, bool)
            or not 0 <= score <= 100
        ):
            raise ExternalServiceError("Внешний сервис вернул некорректную оценку")
        auto_score = float(score)
        mark = auto_score
        if isinstance(external_result.get("feedback"), str):
            feedback = external_result["feedback"]

    review = models.Review(
        submission_id=submission_id,
        reviewer_id=actor_id,
        type=models.ReviewType(payload.type),
        feedback=feedback,
        mark=mark,
        auto_score=auto_score,
        manual=payload.manual,
        status=models.ReviewStatus.COMPLETED,
    )
    session.add(review)
    await session.flush()

    submission.review_id = review.id
    submission.status = models.SubmissionStatus.COMPLETED
    await session.flush()

    response = Review.model_validate(review)
    await _remember_idempotency(session, key, payload_json, response.model_dump())
    return response


async def get_review(
    session: AsyncSession, submission_id: UUID, actor_id: UUID
) -> Review:
    submission = await session.get(models.Submission, submission_id)
    if submission is None or submission.review_id is None:
        raise ReviewNotFoundError()
    if submission.student_id != actor_id:
        raise ForbiddenError()
    review = await session.get(models.Review, submission.review_id)
    if review is None:
        raise ReviewNotFoundError()
    return Review.model_validate(review)


async def update_review(
    session: AsyncSession, submission_id: UUID, payload: ReviewUpdate, actor_id: UUID
) -> Review:
    submission = await session.get(models.Submission, submission_id)
    if submission is None or submission.review_id is None:
        raise ReviewNotFoundError()
    review = await session.get(models.Review, submission.review_id)
    if review is None:
        raise ReviewNotFoundError()
    if review.reviewer_id != actor_id:
        raise ForbiddenError()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    await session.flush()
    return Review.model_validate(review)
