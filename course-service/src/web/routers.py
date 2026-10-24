import logging
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import conint, constr

from src.core import services
from src.web.lifespans import lifespan_service_router
from src.web.schemas import (
    Artifacts,
    Assignment,
    AssignmentCreate,
    AssignmentUpdate,
    Assignments,
    Course,
    CourseCreate,
    CourseStudents,
    CourseUpdate,
    Courses,
    Error,
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

IdempotencyKey = constr(min_length=36, max_length=36)
service_router = APIRouter(
    prefix="/service",
    lifespan=lifespan_service_router,
    tags=["service"],
)


@service_router.get(
    "",
    description="Service info route",
    response_model=ServiceInfo,
    status_code=200,
)
def info() -> ServiceInfo:
    return services.get_service_info()


assignments_router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])


@assignments_router.post(
    "",
    response_model=Assignment,
    status_code=201,
    responses={"401": {"model": Error}, "403": {"model": Error}, "422": {"model": Error}},
)
def create_assignment(
    idempotency_key: IdempotencyKey = Header(..., alias="Idempotency-Key"),
    body: AssignmentCreate = ...,
) -> Union[Assignment, Error]:
    """Создать задание."""
    return services.create_assignment(idempotency_key, body)


@assignments_router.get(
    "",
    response_model=Assignments,
    responses={"401": {"model": Error}},
)
def list_assignments(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    course_id: Optional[UUID] = None,
) -> Union[Assignments, Error]:
    """Получить список заданий."""
    return services.list_assignments(offset, limit, course_id)


@assignments_router.get(
    "/{id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "404": {"model": Error}},
)
def get_assignment(id: UUID) -> Union[Assignment, Error]:
    """Получить задание."""
    return services.get_assignment(id)


@assignments_router.patch(
    "/{id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def update_assignment(id: UUID, body: AssignmentUpdate = ...) -> Union[Assignment, Error]:
    """Частично обновить задание."""
    return services.update_assignment(id, body)


@assignments_router.delete(
    "/{id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def delete_assignment(id: UUID) -> Optional[Error]:
    """Удалить задание."""
    services.delete_assignment(id)
    return None


courses_router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


@courses_router.get(
    "",
    response_model=Courses,
    responses={"401": {"model": Error}},
)
def list_courses(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    sort: Optional[str] = None,
    status: Optional[Status1] = None,
) -> Union[Courses, Error]:
    """Получить список доступных курсов."""
    return services.list_courses(offset, limit, sort, status)


@courses_router.post(
    "",
    response_model=Course,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "409": {"model": Error},
        "422": {"model": Error},
    },
)
def create_course(
    idempotency_key: IdempotencyKey = Header(..., alias="Idempotency-Key"),
    body: CourseCreate = ...,
) -> Union[Course, Error]:
    """Создать новый курс."""
    return services.create_course(idempotency_key, body)


@courses_router.get(
    "/{course_id}/students",
    response_model=CourseStudents,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def get_course_students(course_id: UUID) -> Union[CourseStudents, Error]:
    """Получить студентов курса."""
    return services.get_course_students(course_id)


@courses_router.post(
    "/{course_id}/students/{student_id}",
    response_model=None,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "409": {"model": Error},
    },
)
def enroll_student(course_id: UUID, student_id: UUID) -> Optional[Error]:
    """Записать студента на курс."""
    services.enroll_student(course_id, student_id)
    return None


@courses_router.delete(
    "/{course_id}/students/{student_id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def unenroll_student(course_id: UUID, student_id: UUID) -> Optional[Error]:
    """Удалить студента с курса."""
    services.unenroll_student(course_id, student_id)
    return None


@courses_router.get(
    "/{id}",
    response_model=Course,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def get_course(id: UUID) -> Union[Course, Error]:
    """Получить курс."""
    return services.get_course(id)


@courses_router.patch(
    "/{id}",
    response_model=Course,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
)
def update_course(id: UUID, body: CourseUpdate = ...) -> Union[Course, Error]:
    """Частично обновить курс."""
    return services.update_course(id, body)


@courses_router.delete(
    "/{id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def delete_course(id: UUID) -> Optional[Error]:
    """Удалить курс."""
    services.delete_course(id)
    return None


submissions_router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions"])


@submissions_router.post(
    "",
    response_model=Submission,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
        "429": {"model": Error},
    },
)
def create_submission(
    idempotency_key: IdempotencyKey = Header(..., alias="Idempotency-Key"),
    body: SubmissionCreate = ...,
) -> Union[Submission, Error]:
    """Отправить решение."""
    return services.create_submission(idempotency_key, body)


@submissions_router.get(
    "",
    response_model=Submissions,
    responses={"401": {"model": Error}},
)
def list_submissions(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    assignment_id: Optional[UUID] = None,
) -> Union[Submissions, Error]:
    """Получить список сдач."""
    return services.list_submissions(offset, limit, assignment_id)


@submissions_router.get(
    "/{id}",
    response_model=Submission,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def get_submission(id: UUID) -> Union[Submission, Error]:
    """Получить сдачу."""
    return services.get_submission(id)


@submissions_router.get(
    "/{id}/artifacts",
    response_model=Artifacts,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def get_submission_artifacts(id: UUID) -> Union[Artifacts, Error]:
    """Получить артефакты сдачи."""
    return services.get_submission_artifacts(id)


reviews_router = APIRouter(prefix="/api/v1/submissions", tags=["Reviews"])


@reviews_router.post(
    "/{id}/review",
    response_model=Review,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
)
def create_review(
    idempotency_key: IdempotencyKey = Header(..., alias="Idempotency-Key"),
    id: UUID = ...,
    body: ReviewCreate = ...,
) -> Union[Review, Error]:
    """Проверить сдачу и выставить оценку."""
    return services.create_review(idempotency_key, id, body)


@reviews_router.get(
    "/{id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def get_review(id: UUID) -> Union[Review, Error]:
    """Получить результат проверки."""
    return services.get_review(id)


@reviews_router.patch(
    "/{id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
def update_review(id: UUID, body: ReviewUpdate = ...) -> Union[Review, Error]:
    """Обновить комментарий/оценку."""
    return services.update_review(id, body)


all_routers = (
    service_router,
    assignments_router,
    courses_router,
    submissions_router,
    reviews_router,
)