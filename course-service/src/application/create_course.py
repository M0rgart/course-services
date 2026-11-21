from uuid import UUID

from src.application.ports import UnitOfWork
from src.core import models
from src.web.schemas import Course, CourseCreate


class CreateCourseUseCase:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def execute(self, key: str, payload: CourseCreate, actor_id: UUID) -> Course:
        payload_json = payload.model_dump_json()
        cached = await self._unit_of_work.idempotency.claim(
            key, payload_json, "create_course", actor_id
        )
        if cached is not None:
            return Course.model_validate(cached)
        course = models.Course(
            title=payload.title,
            description=payload.description,
            teacher_id=payload.teacher_id,
            status=models.CourseStatus(payload.status or "DRAFT"),
        )
        await self._unit_of_work.courses.add(course)
        await self._unit_of_work.courses.flush()
        result = Course.model_validate(course)
        await self._unit_of_work.idempotency.remember(
            key, payload_json, result.model_dump(), "create_course", actor_id
        )
        return result
