import asyncio
import tempfile
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from src.core.db import Base
from src.core.models import Assignment, Course

COURSES = 4
ASSIGNMENTS_PER_COURSE = 2


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    today = date.today()
    async with session_factory() as session, session.begin():
        for course_index in range(COURSES):
            course = Course(
                title=f"Демонстрационный курс {course_index}",
                teacher_id=uuid4(),
            )
            session.add(course)
            await session.flush()
            for assignment_index in range(ASSIGNMENTS_PER_COURSE):
                session.add(
                    Assignment(
                        title=f"Задание {course_index}.{assignment_index}",
                        course_id=course.id,
                        submit_limit=3,
                        date_start=today,
                        date_end=today + timedelta(days=7),
                    )
                )


async def _run() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "n_plus_one.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
        session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        statements: list[str] = []

        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def _record_statement(*args: object) -> None:
            statements.append(str(args[2]))

        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await _seed(session_factory)

            statements.clear()
            async with session_factory() as session:
                courses = (await session.execute(select(Course))).scalars().all()
                for course in courses:
                    await course.awaitable_attrs.assignments
            lazy_queries = len(statements)

            statements.clear()
            async with session_factory() as session:
                courses = (
                    (
                        await session.execute(
                            select(Course).options(selectinload(Course.assignments))
                        )
                    )
                    .scalars()
                    .all()
                )
                loaded_assignments = sum(len(course.assignments) for course in courses)
            eager_queries = len(statements)

            print(f"Курсов: {COURSES}, заданий на курс: {ASSIGNMENTS_PER_COURSE}")
            print(f"N+1 (ленивая загрузка awaitable_attrs): {lazy_queries} SQL-запросов")
            print(f"selectinload (одна дополнительная выборка): {eager_queries} SQL-запросов")
            print(f"Загружено заданий: {loaded_assignments}")
            print(f"Формула N+1: 1 + {COURSES} = {1 + COURSES}")
        finally:
            await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
