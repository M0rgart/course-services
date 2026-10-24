from uuid import UUID

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
    Review,
    ReviewCreate,
    ReviewUpdate,
    ServiceInfo,
    Status1,
    Submission,
    SubmissionCreate,
    Submissions,
)


def get_service_info() -> ServiceInfo:
    return ServiceInfo()


def create_assignment(idempotency_key: str, payload: AssignmentCreate) -> Assignment:
    raise NotImplementedError


def list_assignments(
    offset: int,
    limit: int,
    course_id: UUID | None,
) -> Assignments:
    raise NotImplementedError


def get_assignment(assignment_id: UUID) -> Assignment:
    raise NotImplementedError


def update_assignment(assignment_id: UUID, payload: AssignmentUpdate) -> Assignment:
    raise NotImplementedError


def delete_assignment(assignment_id: UUID) -> None:
    raise NotImplementedError


def list_courses(
    offset: int,
    limit: int,
    sort: str | None,
    status: Status1 | None,
) -> Courses:
    raise NotImplementedError


def create_course(idempotency_key: str, payload: CourseCreate) -> Course:
    raise NotImplementedError


def get_course_students(course_id: UUID) -> CourseStudents:
    raise NotImplementedError


def enroll_student(course_id: UUID, student_id: UUID) -> None:
    raise NotImplementedError


def unenroll_student(course_id: UUID, student_id: UUID) -> None:
    raise NotImplementedError


def get_course(course_id: UUID) -> Course:
    raise NotImplementedError


def update_course(course_id: UUID, payload: CourseUpdate) -> Course:
    raise NotImplementedError


def delete_course(course_id: UUID) -> None:
    raise NotImplementedError


def create_submission(idempotency_key: str, payload: SubmissionCreate) -> Submission:
    raise NotImplementedError


def list_submissions(
    offset: int,
    limit: int,
    assignment_id: UUID | None,
) -> Submissions:
    raise NotImplementedError


def get_submission(submission_id: UUID) -> Submission:
    raise NotImplementedError


def get_submission_artifacts(submission_id: UUID) -> Artifacts:
    raise NotImplementedError


def create_review(
    idempotency_key: str,
    submission_id: UUID,
    payload: ReviewCreate,
) -> Review:
    raise NotImplementedError


def get_review(submission_id: UUID) -> Review:
    raise NotImplementedError


def update_review(submission_id: UUID, payload: ReviewUpdate) -> Review:
    raise NotImplementedError