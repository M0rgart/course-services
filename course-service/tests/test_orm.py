from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from src.core.db import Base
from src.core.exceptions import ConflictError
from src.core.models import (
    Assignment,
    Course,
    CourseStudent,
    Review,
    ReviewStatus,
    ReviewType,
    Submission,
    SubmissionAttemptCounter,
    SubmissionStatus,
)
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWorkFactory

COURSES = 4
ASSIGNMENTS_PER_COURSE = 2


async def _prepare_engine(tmp_path: Path):
    database_path = tmp_path / "orm.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


def _session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def _seed(
    session_factory: async_sessionmaker[AsyncSession],
    courses: int = COURSES,
    assignments_per_course: int = ASSIGNMENTS_PER_COURSE,
) -> None:
    today = date.today()
    async with session_factory() as session, session.begin():
        for course_index in range(courses):
            course = Course(title=f"Course {course_index}", teacher_id=uuid4())
            session.add(course)
            await session.flush()
            for assignment_index in range(assignments_per_course):
                session.add(
                    Assignment(
                        title=f"Assignment {course_index}.{assignment_index}",
                        course_id=course.id,
                        submit_limit=3,
                        date_start=today,
                        date_end=today + timedelta(days=7),
                    )
                )


def test_orm_uses_async_attrs_and_expected_cardinality() -> None:
    assert issubclass(Base, AsyncAttrs)
    assert Course.__mapper__.relationships["assignments"].uselist is True
    assert Course.__mapper__.relationships["enrollments"].uselist is True
    assert Assignment.__mapper__.relationships["submissions"].uselist is True
    assert Assignment.__mapper__.relationships["attempt_counters"].uselist is True
    assert SubmissionAttemptCounter.__mapper__.relationships["assignment"].uselist is False
    assert Submission.__mapper__.relationships["review"].uselist is False
    assert Review.__mapper__.relationships["submission"].uselist is False


@pytest.mark.asyncio
async def test_lazy_loading_causes_n_plus_one_and_selectin_fixes_it(tmp_path: Path) -> None:
    engine = await _prepare_engine(tmp_path)
    session_factory = _session_factory(engine)
    await _seed(session_factory)
    statements: list[str] = []

    def _record_statement(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(engine.sync_engine, "before_cursor_execute", _record_statement)
    try:
        statements.clear()
        async with session_factory() as session:
            courses = (await session.execute(select(Course))).scalars().all()
            for course in courses:
                await course.awaitable_attrs.assignments
        lazy_queries = len(statements)
        assert lazy_queries == 1 + COURSES

        statements.clear()
        async with session_factory() as session:
            courses = (
                (await session.execute(select(Course).options(selectinload(Course.assignments))))
                .scalars()
                .all()
            )
            loaded_assignments = sum(len(course.assignments) for course in courses)
        eager_queries = len(statements)
        assert eager_queries == 2
        assert loaded_assignments == COURSES * ASSIGNMENTS_PER_COURSE
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record_statement)
        await engine.dispose()


@pytest.mark.asyncio
async def test_relationships_return_related_entities(tmp_path: Path) -> None:
    engine = await _prepare_engine(tmp_path)
    session_factory = _session_factory(engine)
    teacher_id = uuid4()
    student_id = uuid4()
    today = date.today()

    async with session_factory() as session, session.begin():
        course = Course(title="Relationship course", teacher_id=teacher_id)
        session.add(course)
        await session.flush()
        assignment = Assignment(
            title="Relationship assignment",
            course_id=course.id,
            submit_limit=3,
            date_start=today,
            date_end=today + timedelta(days=7),
        )
        session.add(assignment)
        session.add(CourseStudent(course_id=course.id, student_id=student_id))
        await session.flush()
        submission = Submission(assignment_id=assignment.id, student_id=student_id)
        session.add(submission)
        await session.flush()
        review = Review(
            submission_id=submission.id,
            reviewer_id=teacher_id,
            type=ReviewType.MANUAL,
            feedback="Accepted",
            mark=95.0,
            status=ReviewStatus.COMPLETED,
        )
        session.add(review)
        submission.review_id = review.id
        submission.status = SubmissionStatus.COMPLETED

    async with session_factory() as session:
        loaded_course = (
            await session.execute(select(Course).options(selectinload(Course.assignments)))
        ).scalar_one()
        assert loaded_course.assignments[0].course.id == course.id

        loaded_assignment = (
            await session.execute(
                select(Assignment)
                .where(Assignment.id == assignment.id)
                .options(selectinload(Assignment.submissions))
            )
        ).scalar_one()
        assert loaded_assignment.course.id == course.id
        assert loaded_assignment.submissions[0].id == submission.id

        loaded_submission = (
            await session.execute(select(Submission).where(Submission.id == submission.id))
        ).scalar_one()
        assert loaded_submission.assignment.id == assignment.id
        assert loaded_submission.review is not None
        assert loaded_submission.review.mark == 95.0

        loaded_review = (
            await session.execute(select(Review).where(Review.id == review.id))
        ).scalar_one()
        assert loaded_review.submission.id == submission.id

    await engine.dispose()


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_on_exception(tmp_path: Path) -> None:
    engine = await _prepare_engine(tmp_path)
    factory = SqlAlchemyUnitOfWorkFactory(_session_factory(engine))

    with pytest.raises(RuntimeError):
        async with factory.create() as unit_of_work:
            unit_of_work.repository.add(Course(title="Rollback course", teacher_id=uuid4()))
            await unit_of_work.repository.flush()
            raise RuntimeError("rollback")

    async with factory.create() as unit_of_work:
        courses = (await unit_of_work.repository.execute(select(Course))).scalars().all()
        assert courses == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_unit_of_work_maps_stale_data_error_to_conflict(tmp_path: Path) -> None:
    engine = await _prepare_engine(tmp_path)
    factory = SqlAlchemyUnitOfWorkFactory(_session_factory(engine))
    unit_of_work = factory.create()

    with (
        patch.object(
            unit_of_work.session,
            "commit",
            new=AsyncMock(side_effect=StaleDataError("stale")),
        ),
        pytest.raises(ConflictError) as error,
    ):
        await unit_of_work.commit()

    assert error.value.status == 409
    await unit_of_work.close()
    await engine.dispose()
