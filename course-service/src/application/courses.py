import json
from uuid import UUID

from sqlalchemy import func, select

from src.application.common import (
    _check_idempotency,
    _pagination,
    _remember_idempotency,
    _require_course_access,
)
from src.application.ports import Repository
from src.core import models
from src.core.exceptions import (
    ConflictError,
    CourseNotFoundError,
    ForbiddenError,
    ValidationError,
)
from src.web.schemas import (
    Course,
    CourseReplace,
    Courses,
    CourseStatus,
    CourseStudents,
    CourseUpdate,
)


async def list_courses(
    repository: Repository,
    offset: int,
    limit: int,
    sort: str | None,
    status: CourseStatus | None,
    actor_id: UUID,
    role: str,
) -> Courses:
    stmt = select(models.Course)
    if role == "teacher":
        stmt = stmt.where(models.Course.teacher_id == actor_id)
    elif role == "student":
        stmt = stmt.join(
            models.CourseStudent,
            models.CourseStudent.course_id == models.Course.id,
        ).where(models.CourseStudent.student_id == actor_id)
    if status is not None:
        stmt = stmt.where(models.Course.status == status.value)
    if sort:
        for value in sort.split(","):
            field_name, separator, direction = value.partition(":")
            if separator:
                if direction.lower() not in {"asc", "desc"}:
                    raise ValidationError("Неизвестное направление сортировки")
                descending = direction.lower() == "desc"
            else:
                descending = field_name.startswith("-")
                field_name = field_name.removeprefix("-")
            column = getattr(models.Course, field_name, None)
            if column is None or field_name not in models.Course.__table__.columns:
                raise ValidationError("Неизвестное поле сортировки")
            stmt = stmt.order_by(column.desc() if descending else column.asc())
    total = (
        await repository.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    rows = (await repository.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return Courses(
        data=[Course.model_validate(course) for course in rows],
        pagination=_pagination(total, offset, limit),
    )


async def get_course(repository: Repository, course_id: UUID, actor_id: UUID, role: str) -> Course:
    course = await repository.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    await _require_course_access(repository, course_id, actor_id, role)
    return Course.model_validate(course)


async def update_course(
    repository: Repository,
    course_id: UUID,
    payload: CourseUpdate | CourseReplace,
    actor_id: UUID,
    role: str,
) -> Course:
    course = await repository.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    await _require_course_access(repository, course_id, actor_id, role)
    updates = payload.model_dump(exclude_unset=True)
    if role != "admin" and "teacher_id" in updates:
        raise ForbiddenError()
    for field, value in updates.items():
        setattr(course, field, value)
    await repository.flush()
    return Course.model_validate(course)


async def delete_course(repository: Repository, course_id: UUID) -> None:
    course = await repository.get(models.Course, course_id)
    if course is None:
        raise CourseNotFoundError()
    await repository.delete(course)
    await repository.flush()


async def get_course_students(
    repository: Repository, course_id: UUID, actor_id: UUID, role: str
) -> CourseStudents:
    if await repository.get(models.Course, course_id) is None:
        raise CourseNotFoundError()
    await _require_course_access(repository, course_id, actor_id, role)
    stmt = select(models.CourseStudent.student_id).where(
        models.CourseStudent.course_id == course_id
    )
    student_ids = list((await repository.execute(stmt)).scalars().all())
    return CourseStudents(course_id=course_id, students_ids=student_ids)


async def enroll_student(
    repository: Repository,
    key: str,
    course_id: UUID,
    student_id: UUID,
    actor_id: UUID,
) -> None:
    if await repository.get(models.Course, course_id) is None:
        raise CourseNotFoundError()
    payload = json.dumps({"course_id": str(course_id), "student_id": str(student_id)})
    cached = await _check_idempotency(
        repository, key, payload, f"enroll_student:{course_id}", actor_id
    )
    if cached is not None:
        return
    stmt = select(models.CourseStudent).where(
        models.CourseStudent.course_id == course_id,
        models.CourseStudent.student_id == student_id,
    )
    if (await repository.execute(stmt)).scalar_one_or_none() is not None:
        raise ConflictError("Студент уже записан на курс")
    repository.add(models.CourseStudent(course_id=course_id, student_id=student_id))
    await repository.flush()
    await _remember_idempotency(
        repository, key, payload, {}, f"enroll_student:{course_id}", actor_id
    )


async def unenroll_student(repository: Repository, course_id: UUID, student_id: UUID) -> None:
    if await repository.get(models.Course, course_id) is None:
        raise CourseNotFoundError()
    stmt = select(models.CourseStudent).where(
        models.CourseStudent.course_id == course_id,
        models.CourseStudent.student_id == student_id,
    )
    link = (await repository.execute(stmt)).scalar_one_or_none()
    if link is None:
        raise CourseNotFoundError()
    await repository.delete(link)
