from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import (
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db import Base, UTCDateTime


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


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


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)


class SubmissionAttemptCounter(Base):
    __tablename__ = "submission_attempt_counters"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)

    assignment: Mapped[Assignment] = relationship(
        back_populates="attempt_counters",
        lazy="joined",
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    claimed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4096))
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, native_enum=False), default=CourseStatus.DRAFT, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, onupdate=_utcnow)

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Assignment.created_at",
    )
    enrollments: Mapped[list[CourseStudent]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )


class CourseStudent(Base):
    __tablename__ = "course_students"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)

    course: Mapped[Course] = relationship(back_populates="enrollments", lazy="joined")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4096))
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    submit_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    date_start: Mapped[date] = mapped_column(Date, nullable=False)
    date_end: Mapped[date] = mapped_column(Date, nullable=False)
    materials_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow, onupdate=_utcnow)

    course: Mapped[Course] = relationship(back_populates="assignments", lazy="joined")
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="Submission.submitted_at",
    )
    attempt_counters: Mapped[list[SubmissionAttemptCounter]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    review_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(2048))
    artifacts_url: Mapped[str | None] = mapped_column(String(2048))
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, native_enum=False), default=SubmissionStatus.SUBMITTED
    )

    assignment: Mapped[Assignment] = relationship(back_populates="submissions", lazy="joined")
    review: Mapped[Review | None] = relationship(
        back_populates="submission",
        uselist=False,
        lazy="joined",
        cascade="all, delete-orphan",
        single_parent=True,
        passive_deletes=True,
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), unique=True
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[ReviewType] = mapped_column(Enum(ReviewType, native_enum=False))
    feedback: Mapped[str | None] = mapped_column(String(4096))
    mark: Mapped[float] = mapped_column(Float, nullable=False)
    auto_score: Mapped[float | None] = mapped_column(Float)
    manual: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=_utcnow)
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False), default=ReviewStatus.PROCESSING
    )

    submission: Mapped[Submission] = relationship(back_populates="review", lazy="joined")
