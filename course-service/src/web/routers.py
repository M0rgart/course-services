import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.core import services
from src.core.db import SessionDep
from src.core.security import CurrentUserDep, TeacherDep
from src.web.dependencies import ExternalServiceDep, IdempotencyKey, Page, get_page
from src.web.lifespans import lifespan_service_router
from src.web.schemas import (
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

PageDep = Annotated[Page, Depends(get_page)]

service_router = APIRouter(
    prefix="/service", lifespan=lifespan_service_router, tags=["service"]
)


@service_router.get("", response_model=ServiceInfo, status_code=200)
def info() -> ServiceInfo:
    return services.get_service_info()


assignments_router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])


@assignments_router.post(
    "",
    response_model=Assignment,
    status_code=201,
    responses={"401": {"model": Error}, "403": {"model": Error}, "422": {"model": Error}},
)
async def create_assignment(
    idempotency_key: IdempotencyKey,
    body: AssignmentCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> Assignment:
    return await services.create_assignment(session, idempotency_key, body, user.id)


@assignments_router.get(
    "", response_model=Assignments, responses={"401": {"model": Error}}
)
async def list_assignments(
    _user: CurrentUserDep,
    page: PageDep,
    session: SessionDep,
    course_id: UUID | None = None,
) -> Assignments:
    return await services.list_assignments(session, page.offset, page.limit, course_id)


@assignments_router.get(
    "/{id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "404": {"model": Error}},
)
async def get_assignment(
    id: UUID, _user: CurrentUserDep, session: SessionDep
) -> Assignment:
    return await services.get_assignment(session, id)


@assignments_router.patch(
    "/{id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def update_assignment(
    id: UUID,
    body: AssignmentUpdate,
    user: TeacherDep,
    session: SessionDep,
) -> Assignment:
    return await services.update_assignment(session, id, body, user.id)


@assignments_router.delete(
    "/{id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def delete_assignment(id: UUID, user: TeacherDep, session: SessionDep) -> None:
    await services.delete_assignment(session, id, user.id)


courses_router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


@courses_router.get("", response_model=Courses, responses={"401": {"model": Error}})
async def list_courses(
    _user: CurrentUserDep,
    page: PageDep,
    session: SessionDep,
    sort: str | None = None,
    status: Status1 | None = None,
) -> Courses:
    return await services.list_courses(session, page.offset, page.limit, sort, status)


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
async def create_course(
    idempotency_key: IdempotencyKey,
    body: CourseCreate,
    user: TeacherDep,
    session: SessionDep,
) -> Course:
    return await services.create_course(session, idempotency_key, body, user.id)


@courses_router.get(
    "/{course_id}/students",
    response_model=CourseStudents,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_course_students(
    course_id: UUID, _user: CurrentUserDep, session: SessionDep
) -> CourseStudents:
    return await services.get_course_students(session, course_id)


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
async def enroll_student(
    course_id: UUID,
    student_id: UUID,
    user: TeacherDep,
    session: SessionDep,
) -> None:
    await services.enroll_student(session, course_id, student_id, user.id)


@courses_router.delete(
    "/{course_id}/students/{student_id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def unenroll_student(
    course_id: UUID,
    student_id: UUID,
    user: TeacherDep,
    session: SessionDep,
) -> None:
    await services.unenroll_student(session, course_id, student_id, user.id)


@courses_router.get(
    "/{id}",
    response_model=Course,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_course(id: UUID, _user: CurrentUserDep, session: SessionDep) -> Course:
    return await services.get_course(session, id)


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
async def update_course(
    id: UUID, body: CourseUpdate, user: TeacherDep, session: SessionDep
) -> Course:
    return await services.update_course(session, id, body, user.id)


@courses_router.delete(
    "/{id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def delete_course(id: UUID, user: TeacherDep, session: SessionDep) -> None:
    await services.delete_course(session, id, user.id)


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
async def create_submission(
    idempotency_key: IdempotencyKey,
    body: SubmissionCreate,
    user: CurrentUserDep,
    session: SessionDep,
) -> Submission:
    return await services.create_submission(session, idempotency_key, body, user.id)


@submissions_router.get(
    "", response_model=Submissions, responses={"401": {"model": Error}}
)
async def list_submissions(
    user: CurrentUserDep,
    page: PageDep,
    session: SessionDep,
    assignment_id: UUID | None = None,
) -> Submissions:
    return await services.list_submissions(
        session, page.offset, page.limit, assignment_id, user.id
    )


@submissions_router.get(
    "/{id}",
    response_model=Submission,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_submission(
    id: UUID, user: CurrentUserDep, session: SessionDep
) -> Submission:
    return await services.get_submission(session, id, user.id)


@submissions_router.get(
    "/{id}/artifacts",
    response_model=Artifacts,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_submission_artifacts(
    id: UUID, user: CurrentUserDep, session: SessionDep
) -> Artifacts:
    return await services.get_submission_artifacts(session, id, user.id)


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
        "502": {"model": Error},
        "504": {"model": Error},
    },
)
async def create_review(
    id: UUID,
    idempotency_key: IdempotencyKey,
    body: ReviewCreate,
    user: TeacherDep,
    session: SessionDep,
    external_service: ExternalServiceDep,
) -> Review:
    return await services.create_review(
        session, idempotency_key, id, body, user.id, external_service
    )


@reviews_router.get(
    "/{id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_review(
    id: UUID, user: CurrentUserDep, session: SessionDep
) -> Review:
    return await services.get_review(session, id, user.id)


@reviews_router.patch(
    "/{id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def update_review(
    id: UUID,
    body: ReviewUpdate,
    user: TeacherDep,
    session: SessionDep,
) -> Review:
    return await services.update_review(session, id, body, user.id)


all_routers = (
    service_router,
    assignments_router,
    courses_router,
    submissions_router,
    reviews_router,
)
