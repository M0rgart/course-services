from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.application import assignments, common, courses, reviews, submissions
from src.application.create_course import CreateCourseUseCase
from src.core.security import AdminDep, CurrentUserDep, StudentDep, TeacherDep
from src.web.dependencies import (
    ExternalServiceDep,
    IdempotencyKey,
    Page,
    RepositoryDep,
    UnitOfWorkDep,
    get_page,
)
from src.web.lifespans import lifespan_service_router
from src.web.schemas import (
    Artifacts,
    Assignment,
    AssignmentCreate,
    Assignments,
    AssignmentUpdate,
    Course,
    CourseCreate,
    CourseReplace,
    Courses,
    CourseStatus,
    CourseStudents,
    CourseUpdate,
    Error,
    Review,
    ReviewCreate,
    ReviewUpdate,
    ServiceInfo,
    Submission,
    SubmissionCreate,
    Submissions,
)

PageDep = Annotated[Page, Depends(get_page)]

service_router = APIRouter(prefix="/service", lifespan=lifespan_service_router, tags=["service"])
assignments_router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])
courses_router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])
submissions_router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions"])
reviews_router = APIRouter(prefix="/api/v1/submissions", tags=["Reviews"])


@service_router.get("", response_model=ServiceInfo, status_code=200)
def service_info() -> ServiceInfo:
    return common.get_service_info()


@assignments_router.post(
    "",
    response_model=Assignment,
    status_code=201,
    responses={"401": {"model": Error}, "403": {"model": Error}, "422": {"model": Error}},
)
async def create_assignment(
    idempotency_key: IdempotencyKey,
    body: AssignmentCreate,
    user: TeacherDep,
    repository: RepositoryDep,
) -> Assignment:
    return await assignments.create_assignment(
        repository, str(idempotency_key), body, user.id, user.role
    )


@assignments_router.get("", response_model=Assignments, responses={"401": {"model": Error}})
async def list_assignments(
    user: CurrentUserDep,
    page: PageDep,
    repository: RepositoryDep,
    course_id: UUID | None = None,
) -> Assignments:
    return await assignments.list_assignments(
        repository, page.offset, page.limit, course_id, user.id, user.role
    )


@assignments_router.get(
    "/{assignment_id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_assignment(
    assignment_id: UUID, user: CurrentUserDep, repository: RepositoryDep
) -> Assignment:
    return await assignments.get_assignment(repository, assignment_id, user.id, user.role)


@assignments_router.patch(
    "/{assignment_id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def update_assignment(
    assignment_id: UUID,
    body: AssignmentUpdate,
    user: TeacherDep,
    repository: RepositoryDep,
) -> Assignment:
    return await assignments.update_assignment(repository, assignment_id, body, user.id, user.role)


@assignments_router.delete(
    "/{assignment_id}",
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def delete_assignment(
    assignment_id: UUID, user: TeacherDep, repository: RepositoryDep
) -> None:
    await assignments.delete_assignment(repository, assignment_id, user.id, user.role)


@courses_router.get("", response_model=Courses, responses={"401": {"model": Error}})
async def list_courses(
    user: CurrentUserDep,
    page: PageDep,
    repository: RepositoryDep,
    sort: str | None = None,
    status: CourseStatus | None = None,
) -> Courses:
    return await courses.list_courses(
        repository, page.offset, page.limit, sort, status, user.id, user.role
    )


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
    user: AdminDep,
    unit_of_work: UnitOfWorkDep,
) -> Course:
    return await CreateCourseUseCase(unit_of_work).execute(str(idempotency_key), body, user.id)


@courses_router.get(
    "/{course_id}/students",
    response_model=CourseStudents,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_course_students(
    course_id: UUID, user: TeacherDep, repository: RepositoryDep
) -> CourseStudents:
    return await courses.get_course_students(repository, course_id, user.id, user.role)


@courses_router.post(
    "/{course_id}/students/{student_id}",
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
    idempotency_key: IdempotencyKey,
    _user: AdminDep,
    repository: RepositoryDep,
) -> None:
    await courses.enroll_student(repository, str(idempotency_key), course_id, student_id, _user.id)


@courses_router.delete(
    "/{course_id}/students/{student_id}",
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def unenroll_student(
    course_id: UUID,
    student_id: UUID,
    _user: AdminDep,
    repository: RepositoryDep,
) -> None:
    await courses.unenroll_student(repository, course_id, student_id)


@courses_router.get(
    "/{course_id}",
    response_model=Course,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_course(course_id: UUID, user: CurrentUserDep, repository: RepositoryDep) -> Course:
    return await courses.get_course(repository, course_id, user.id, user.role)


@courses_router.patch(
    "/{course_id}",
    response_model=Course,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
)
async def update_course(
    course_id: UUID,
    body: CourseUpdate,
    user: TeacherDep,
    repository: RepositoryDep,
) -> Course:
    return await courses.update_course(repository, course_id, body, user.id, user.role)


@courses_router.put(
    "/{course_id}",
    response_model=Course,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
)
async def replace_course(
    course_id: UUID,
    body: CourseReplace,
    user: AdminDep,
    repository: RepositoryDep,
) -> Course:
    return await courses.update_course(repository, course_id, body, user.id, user.role)


@courses_router.delete(
    "/{course_id}",
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def delete_course(course_id: UUID, _user: AdminDep, repository: RepositoryDep) -> None:
    await courses.delete_course(repository, course_id)


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
    user: StudentDep,
    unit_of_work: UnitOfWorkDep,
) -> Submission:
    return await submissions.create_submission(
        unit_of_work.repository,
        str(idempotency_key),
        body,
        user.id,
        unit_of_work.outbox,
    )


@submissions_router.get("", response_model=Submissions, responses={"401": {"model": Error}})
async def list_submissions(
    user: CurrentUserDep,
    page: PageDep,
    repository: RepositoryDep,
    assignment_id: UUID | None = None,
) -> Submissions:
    return await submissions.list_submissions(
        repository, page.offset, page.limit, assignment_id, user.id, user.role
    )


@submissions_router.get(
    "/{submission_id}",
    response_model=Submission,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_submission(
    submission_id: UUID, user: CurrentUserDep, repository: RepositoryDep
) -> Submission:
    return await submissions.get_submission(repository, submission_id, user.id, user.role)


@submissions_router.get(
    "/{submission_id}/artifacts",
    response_model=Artifacts,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_submission_artifacts(
    submission_id: UUID, user: CurrentUserDep, repository: RepositoryDep
) -> Artifacts:
    return await submissions.get_submission_artifacts(repository, submission_id, user.id, user.role)


@reviews_router.post(
    "/{submission_id}/review",
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
    submission_id: UUID,
    idempotency_key: IdempotencyKey,
    body: ReviewCreate,
    user: TeacherDep,
    repository: RepositoryDep,
    external_service: ExternalServiceDep,
) -> Review:
    return await reviews.create_review(
        repository,
        str(idempotency_key),
        submission_id,
        body,
        user.id,
        user.role,
        external_service,
    )


@reviews_router.get(
    "/{submission_id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def get_review(
    submission_id: UUID, user: CurrentUserDep, repository: RepositoryDep
) -> Review:
    return await reviews.get_review(repository, submission_id, user.id, user.role)


@reviews_router.patch(
    "/{submission_id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
)
async def update_review(
    submission_id: UUID,
    body: ReviewUpdate,
    user: TeacherDep,
    repository: RepositoryDep,
) -> Review:
    return await reviews.update_review(repository, submission_id, body, user.id, user.role)


all_routers = (
    service_router,
    assignments_router,
    courses_router,
    submissions_router,
    reviews_router,
)
