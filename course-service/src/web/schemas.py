from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    confloat,
    conint,
    constr,
)


class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ServiceInfo(BaseSchemaModel):
    healthy: bool = True


class CourseStatus(Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class Status1(Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class SubmissionStatus(Enum):
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewType(Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class ReviewStatus(Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class ErrorDetail(BaseSchemaModel):
    code: str = Field(..., examples=["COURSE_NOT_FOUND"])
    message: str = Field(..., examples=["Курс не существует"])
    status: int = Field(..., examples=[404])
    path: str = Field(..., examples=["/api/v1/courses/"])
    request_id: UUID


class Error(BaseSchemaModel):
    error: ErrorDetail


class Pagination(BaseSchemaModel):
    offset: int
    limit: int
    total: int


class CourseCreate(BaseSchemaModel):
    model_config = ConfigDict(extra="forbid")

    title: constr(min_length=15, max_length=255)
    description: Optional[constr(min_length=2, max_length=4096)] = None
    teacher_id: UUID
    status: Optional[CourseStatus] = None


class CourseUpdate(BaseSchemaModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[constr(min_length=15, max_length=255)] = None
    description: Optional[constr(min_length=2, max_length=4096)] = None
    teacher_id: Optional[UUID] = None
    status: Optional[CourseStatus] = None


class Course(CourseCreate):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Courses(BaseSchemaModel):
    data: List[Course]
    pagination: Pagination


class CourseStudents(BaseSchemaModel):
    course_id: UUID
    students_ids: List[UUID]


class AssignmentCreate(BaseSchemaModel):
    title: constr(min_length=8, max_length=255)
    description: Optional[constr(max_length=4096)] = None
    course_id: UUID
    submit_limit: conint(ge=3, le=10) = Field(..., examples=[3])
    date_start: date = Field(..., examples=["2026-09-01"])
    date_end: date = Field(..., examples=["2026-12-31"])
    materials_url: Optional[AnyUrl] = None


class AssignmentUpdate(BaseSchemaModel):
    title: Optional[constr(min_length=8, max_length=255)] = None
    description: Optional[constr(max_length=4096)] = None
    submit_limit: Optional[conint(ge=3, le=10)] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    materials_url: Optional[AnyUrl] = None


class Assignment(AssignmentCreate):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class Assignments(BaseSchemaModel):
    data: List[Assignment]
    pagination: Pagination


class SubmissionCreate(BaseSchemaModel):
    assignment_id: UUID
    repository_url: Optional[AnyUrl] = None
    artifacts_url: Optional[AnyUrl] = None


class Submission(BaseSchemaModel):
    id: UUID
    assignment_id: UUID
    student_id: UUID
    review_id: Optional[UUID] = None
    repository_url: Optional[AnyUrl] = None
    artifacts_url: Optional[AnyUrl] = None
    submitted_at: AwareDatetime
    status: SubmissionStatus


class Submissions(BaseSchemaModel):
    data: List[Submission]
    pagination: Pagination


class Artifact(BaseSchemaModel):
    id: UUID
    submission_id: UUID
    url: AnyUrl
    type: Optional[str] = Field(None, examples=["file"])


class Artifacts(BaseSchemaModel):
    data: List[Artifact]


class ReviewCreate(BaseSchemaModel):
    type: ReviewType = Field(..., examples=["MANUAL"])
    feedback: Optional[constr(max_length=4096)] = None
    mark: confloat(ge=0.0, le=100.0)
    auto_score: Optional[confloat(ge=0.0, le=100.0)] = None
    manual: Optional[confloat(ge=0.0, le=100.0)] = None


class ReviewUpdate(BaseSchemaModel):
    feedback: Optional[constr(max_length=4096)] = None
    mark: Optional[confloat(ge=0.0, le=100.0)] = None
    manual: Optional[confloat(ge=0.0, le=100.0)] = None


class Review(ReviewCreate):
    id: UUID
    submission_id: UUID
    reviewer_id: UUID
    created_at: AwareDatetime
    status: ReviewStatus