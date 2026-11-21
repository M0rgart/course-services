from uuid import UUID

from sqlalchemy import func, select

from src.application.common import (
    _check_idempotency,
    _pagination,
    _remember_idempotency,
    _require_assignment_access,
)
from src.application.ports import Repository
from src.core import models
from src.core.exceptions import (
    AssignmentNotFoundError,
    CourseNotFoundError,
    ForbiddenError,
    ValidationError,
)
from src.web.schemas import (
    Assignment,
    AssignmentCreate,
    Assignments,
    AssignmentUpdate,
)


async def list_assignments(
    repository: Repository,
    offset: int,
    limit: int,
    course_id: UUID | None,
    actor_id: UUID,
    role: str,
) -> Assignments:
    stmt = select(models.Assignment).join(
        models.Course, models.Course.id == models.Assignment.course_id
    )
    if course_id is not None:
        stmt = stmt.where(models.Assignment.course_id == course_id)
    if role == "teacher":
        stmt = stmt.where(models.Course.teacher_id == actor_id)
    elif role == "student":
        stmt = stmt.join(
            models.CourseStudent,
            models.CourseStudent.course_id == models.Course.id,
        ).where(models.CourseStudent.student_id == actor_id)
    total = (
        await repository.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await repository.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Assignments(
        data=[Assignment.model_validate(assignment) for assignment in rows],
        pagination=_pagination(total, offset, limit),
    )


async def create_assignment(
    repository: Repository,
    key: str,
    payload: AssignmentCreate,
    actor_id: UUID,
    role: str,
) -> Assignment:
    course = await repository.get(models.Course, payload.course_id)
    if course is None:
        raise CourseNotFoundError()
    if role != "admin" and course.teacher_id != actor_id:
        raise ForbiddenError()
    if payload.date_end < payload.date_start:
        raise ValidationError("Дата окончания должна быть не раньше даты начала")
    payload_json = payload.model_dump_json()
    cached = await _check_idempotency(repository, key, payload_json, "create_assignment", actor_id)
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
    repository.add(assignment)
    await repository.flush()
    result = Assignment.model_validate(assignment)
    await _remember_idempotency(
        repository, key, payload_json, result.model_dump(), "create_assignment", actor_id
    )
    return result


async def get_assignment(
    repository: Repository, assignment_id: UUID, actor_id: UUID, role: str
) -> Assignment:
    assignment = await repository.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    await _require_assignment_access(repository, assignment, actor_id, role)
    return Assignment.model_validate(assignment)


async def update_assignment(
    repository: Repository,
    assignment_id: UUID,
    payload: AssignmentUpdate,
    actor_id: UUID,
    role: str,
) -> Assignment:
    assignment = await repository.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    course = await repository.get(models.Course, assignment.course_id)
    if course is None or (role != "admin" and course.teacher_id != actor_id):
        raise ForbiddenError()
    updates = payload.model_dump(exclude_unset=True)
    if "materials_url" in updates and updates["materials_url"] is not None:
        updates["materials_url"] = str(updates["materials_url"])
    for field, value in updates.items():
        setattr(assignment, field, value)
    if assignment.date_end < assignment.date_start:
        raise ValidationError("Дата окончания должна быть не раньше даты начала")
    await repository.flush()
    return Assignment.model_validate(assignment)


async def delete_assignment(
    repository: Repository, assignment_id: UUID, actor_id: UUID, role: str
) -> None:
    assignment = await repository.get(models.Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError()
    course = await repository.get(models.Course, assignment.course_id)
    if course is None or (role != "admin" and course.teacher_id != actor_id):
        raise ForbiddenError()
    await repository.delete(assignment)
    await repository.flush()
