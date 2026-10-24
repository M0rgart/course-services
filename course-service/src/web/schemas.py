from datetime import date
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AnyUrl, AwareDatetime, BaseModel, ConfigDict, Field

Title15 = Annotated[str, Field(min_length=15, max_length=255)]
Title8 = Annotated[str, Field(min_length=8, max_length=255)]
Description4096 = Annotated[str, Field(max_length=4096)]
DescriptionMin2 = Annotated[str, Field(min_length=2, max_length=4096)]
SubmitLimit = Annotated[int, Field(ge=3, le=10)]
Mark = Annotated[float, Field(ge=0.0, le=100.0)]


class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ServiceInfo(BaseSchemaModel):
    healthy: bool = True


class CourseStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class SubmissionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewType(StrEnum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class ReviewStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class Status1(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class ErrorDetail(BaseSchemaModel):
    code: str
    message: str
    status: int
    path: str
    request_id: UUID


class Error(BaseSchemaModel):
    error: ErrorDetail


class Pagination(BaseSchemaModel):
    offset: int
    limit: int
    total: int


class CourseCreate(BaseSchemaModel):
    model_config = ConfigDict(extra="forbid")

    title: Title15
    description: DescriptionMin2 | None = None
    teacher_id: UUID
    status: CourseStatus | None = None


class CourseUpdate(BaseSchemaModel):
    model_config = ConfigDict(extra="forbid")

    title: Title15 | None = None
    description: DescriptionMin2 | None = None
    teacher_id: UUID | None = None
    status: CourseStatus | None = None


class Course(CourseCreate):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        populate_by_name=True,
        extra="ignore",
    )

    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Courses(BaseSchemaModel):
    data: list[Course]
    pagination: Pagination


class CourseStudents(BaseSchemaModel):
    course_id: UUID
    students_ids: list[UUID]


class AssignmentCreate(BaseSchemaModel):
    title: Title8
    description: Description4096 | None = None
    course_id: UUID
    submit_limit: SubmitLimit
    date_start: date
    date_end: date
    materials_url: AnyUrl | None = None


class AssignmentUpdate(BaseSchemaModel):
    title: Title8 | None = None
    description: Description4096 | None = None
    submit_limit: SubmitLimit | None = None
    date_start: date | None = None
    date_end: date | None = None
    materials_url: AnyUrl | None = None


class Assignment(AssignmentCreate):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Assignments(BaseSchemaModel):
    data: list[Assignment]
    pagination: Pagination


class SubmissionCreate(BaseSchemaModel):
    assignment_id: UUID
    repository_url: AnyUrl | None = None
    artifacts_url: AnyUrl | None = None


class Submission(BaseSchemaModel):
    id: UUID
    assignment_id: UUID
    student_id: UUID
    review_id: UUID | None = None
    repository_url: AnyUrl | None = None
    artifacts_url: AnyUrl | None = None
    submitted_at: AwareDatetime
    status: SubmissionStatus


class Submissions(BaseSchemaModel):
    data: list[Submission]
    pagination: Pagination


class Artifact(BaseSchemaModel):
    id: UUID
    submission_id: UUID
    url: AnyUrl
    type: str | None = None


class Artifacts(BaseSchemaModel):
    data: list[Artifact]


class ReviewCreate(BaseSchemaModel):
    type: ReviewType
    feedback: Description4096 | None = None
    mark: Mark
    auto_score: Mark | None = None
    manual: Mark | None = None


class ReviewUpdate(BaseSchemaModel):
    feedback: Description4096 | None = None
    mark: Mark | None = None
    manual: Mark | None = None


class Review(ReviewCreate):
    id: UUID
    submission_id: UUID
    reviewer_id: UUID
    created_at: AwareDatetime
    status: ReviewStatus