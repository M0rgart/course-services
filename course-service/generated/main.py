from __future__ import annotations

from typing import Optional, Union
from uuid import UUID

from fastapi import FastAPI, Header
from pydantic import conint

from .models import (
    Artifacts,
    Assignment,
    AssignmentCreate,
    Assignments,
    AssignmentUpdate,
    Course,
    CourseCreate,
    CourseReplace,
    Courses,
    CourseStudents,
    CourseUpdate,
    Error,
    Review,
    ReviewCreate,
    ReviewUpdate,
    ServiceGetResponse,
    Status1,
    Submission,
    SubmissionCreate,
    Submissions,
)

app = FastAPI(
    version="1.0.0",
    title="Course service",
    description="Course service API",
    contact={"name": "Тех. поддержка", "email": "support@yandex.ru"},
    servers=[{"url": "http://127.0.0.1:8888", "description": "Development"}],
)


@app.post(
    "/api/v1/assignments",
    response_model=Assignment,
    status_code=201,
    responses={"401": {"model": Error}, "403": {"model": Error}, "422": {"model": Error}},
    tags=["Assignments"],
)
def post_api_v1_assignments(
    idempotency__key: UUID = Header(..., alias="Idempotency-Key"), body: AssignmentCreate = ...
) -> Union[Assignment, Error]:
    pass


@app.get(
    "/api/v1/assignments",
    response_model=Assignments,
    responses={"401": {"model": Error}},
    tags=["Assignments"],
)
def get_api_v1_assignments(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    course_id: Optional[UUID] = None,
) -> Union[Assignments, Error]:
    pass


@app.get(
    "/api/v1/assignments/{assignment_id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "404": {"model": Error}},
    tags=["Assignments"],
)
def get_api_v1_assignments_assignment_id(assignment_id: UUID) -> Union[Assignment, Error]:
    pass


@app.patch(
    "/api/v1/assignments/{assignment_id}",
    response_model=Assignment,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Assignments"],
)
def patch_api_v1_assignments_assignment_id(
    assignment_id: UUID, body: AssignmentUpdate = ...
) -> Union[Assignment, Error]:
    pass


@app.delete(
    "/api/v1/assignments/{assignment_id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Assignments"],
)
def delete_api_v1_assignments_assignment_id(assignment_id: UUID) -> Optional[Error]:
    pass


@app.get(
    "/api/v1/courses", response_model=Courses, responses={"401": {"model": Error}}, tags=["Courses"]
)
def get_api_v1_courses(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    sort: Optional[str] = None,
    status: Optional[Status1] = None,
) -> Union[Courses, Error]:
    pass


@app.post(
    "/api/v1/courses",
    response_model=Course,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "409": {"model": Error},
        "422": {"model": Error},
    },
    tags=["Courses"],
)
def post_api_v1_courses(
    idempotency__key: UUID = Header(..., alias="Idempotency-Key"), body: CourseCreate = ...
) -> Union[Course, Error]:
    pass


@app.get(
    "/api/v1/courses/{course_id}",
    response_model=Course,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Courses"],
)
def get_api_v1_courses_course_id(course_id: UUID) -> Union[Course, Error]:
    pass


@app.patch(
    "/api/v1/courses/{course_id}",
    response_model=Course,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
    tags=["Courses"],
)
def patch_api_v1_courses_course_id(
    course_id: UUID, body: CourseUpdate = ...
) -> Union[Course, Error]:
    pass


@app.put(
    "/api/v1/courses/{course_id}",
    response_model=Course,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
    },
    tags=["Courses"],
)
def put_api_v1_courses_course_id(
    course_id: UUID, body: CourseReplace = ...
) -> Union[Course, Error]:
    pass


@app.delete(
    "/api/v1/courses/{course_id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Courses"],
)
def delete_api_v1_courses_course_id(course_id: UUID) -> Optional[Error]:
    pass


@app.get(
    "/api/v1/courses/{course_id}/students",
    response_model=CourseStudents,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Courses"],
)
def get_api_v1_courses_course_id_students(course_id: UUID) -> Union[CourseStudents, Error]:
    pass


@app.post(
    "/api/v1/courses/{course_id}/students/{student_id}",
    response_model=None,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "409": {"model": Error},
    },
    tags=["Courses"],
)
def post_api_v1_courses_course_id_students_student_id(
    idempotency__key: UUID = Header(..., alias="Idempotency-Key"),
    course_id: UUID = ...,
    student_id: UUID = ...,
) -> Optional[Error]:
    pass


@app.delete(
    "/api/v1/courses/{course_id}/students/{student_id}",
    response_model=None,
    status_code=204,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Courses"],
)
def delete_api_v1_courses_course_id_students_student_id(
    course_id: UUID, student_id: UUID = ...
) -> Optional[Error]:
    pass


@app.post(
    "/api/v1/submissions",
    response_model=Submission,
    status_code=201,
    responses={
        "401": {"model": Error},
        "403": {"model": Error},
        "404": {"model": Error},
        "422": {"model": Error},
        "429": {"model": Error},
    },
    tags=["Submissions"],
)
def post_api_v1_submissions(
    idempotency__key: UUID = Header(..., alias="Idempotency-Key"), body: SubmissionCreate = ...
) -> Union[Submission, Error]:
    pass


@app.get(
    "/api/v1/submissions",
    response_model=Submissions,
    responses={"401": {"model": Error}},
    tags=["Submissions"],
)
def get_api_v1_submissions(
    offset: Optional[conint(ge=0)] = 0,
    limit: Optional[conint(ge=1, le=100)] = 10,
    assignment_id: Optional[UUID] = None,
) -> Union[Submissions, Error]:
    pass


@app.get(
    "/api/v1/submissions/{submission_id}",
    response_model=Submission,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Submissions"],
)
def get_api_v1_submissions_submission_id(submission_id: UUID) -> Union[Submission, Error]:
    pass


@app.get(
    "/api/v1/submissions/{submission_id}/artifacts",
    response_model=Artifacts,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Submissions"],
)
def get_api_v1_submissions_submission_id_artifacts(submission_id: UUID) -> Union[Artifacts, Error]:
    pass


@app.post(
    "/api/v1/submissions/{submission_id}/review",
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
    tags=["Reviews"],
)
def post_api_v1_submissions_submission_id_review(
    idempotency__key: UUID = Header(..., alias="Idempotency-Key"),
    submission_id: UUID = ...,
    body: ReviewCreate = ...,
) -> Union[Review, Error]:
    pass


@app.get(
    "/api/v1/submissions/{submission_id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Reviews"],
)
def get_api_v1_submissions_submission_id_review(submission_id: UUID) -> Union[Review, Error]:
    pass


@app.patch(
    "/api/v1/submissions/{submission_id}/review",
    response_model=Review,
    responses={"401": {"model": Error}, "403": {"model": Error}, "404": {"model": Error}},
    tags=["Reviews"],
)
def patch_api_v1_submissions_submission_id_review(
    submission_id: UUID, body: ReviewUpdate = ...
) -> Union[Review, Error]:
    pass


@app.get("/service", response_model=ServiceGetResponse, tags=["service"])
def get_service() -> ServiceGetResponse:
    pass
