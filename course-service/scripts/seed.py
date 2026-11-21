import argparse
import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import delete, func, select

from src.core import models
from src.core.config import Settings, get_settings
from src.core.db import Database
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWorkFactory

ADMIN_ID = UUID("00000000-0000-0000-0000-000000000001")
TEACHER_ID = UUID("00000000-0000-0000-0000-000000000002")
SECOND_TEACHER_ID = UUID("00000000-0000-0000-0000-000000000003")
STUDENT_ID = UUID("00000000-0000-0000-0000-000000000010")
SECOND_STUDENT_ID = UUID("00000000-0000-0000-0000-000000000011")

COURSE_ID = UUID("10000000-0000-0000-0000-000000000001")
SECOND_COURSE_ID = UUID("10000000-0000-0000-0000-000000000002")
ASSIGNMENT_ID = UUID("20000000-0000-0000-0000-000000000001")
SECOND_ASSIGNMENT_ID = UUID("20000000-0000-0000-0000-000000000002")
THIRD_ASSIGNMENT_ID = UUID("20000000-0000-0000-0000-000000000003")
SUBMISSION_ID = UUID("30000000-0000-0000-0000-000000000001")
REVIEW_ID = UUID("40000000-0000-0000-0000-000000000001")
OUTBOX_ID = UUID("50000000-0000-0000-0000-000000000001")


def _delete_order() -> tuple[type, ...]:
    return (
        models.Review,
        models.Submission,
        models.SubmissionAttemptCounter,
        models.Assignment,
        models.CourseStudent,
        models.Course,
        models.OutboxEvent,
        models.IdempotencyRecord,
    )


def _token(settings: Settings, user_id: UUID, role: str) -> str:
    now = datetime.now(tz=UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "iss": settings.jwt.issuer,
            "aud": settings.jwt.audience,
            "exp": int((now + timedelta(hours=8)).timestamp()),
        },
        settings.jwt.secret,
        algorithm=settings.jwt.algorithm,
    )


async def seed(reset: bool) -> None:
    settings = get_settings()
    database = Database(settings)
    unit_of_work_factory = SqlAlchemyUnitOfWorkFactory(database.session_factory)
    try:
        async with unit_of_work_factory.create() as unit_of_work:
            if reset:
                for entity_type in _delete_order():
                    await unit_of_work.repository.execute(delete(entity_type))
            existing = (
                await unit_of_work.repository.execute(
                    select(func.count()).select_from(models.Course)
                )
            ).scalar_one()
            if existing and not reset:
                print("База уже содержит курсы. Запустите с --reset, чтобы пересоздать данные.")
                return

            today = date.today()
            first_course = models.Course(
                id=COURSE_ID,
                title="Backend-разработка на Python",
                description=(
                    "Практический курс по проектированию и разработке backend-сервисов "
                    "на Python: FastAPI, SQLAlchemy, миграции, тесты и архитектура."
                ),
                teacher_id=TEACHER_ID,
                status=models.CourseStatus.ACTIVE,
            )
            second_course = models.Course(
                id=SECOND_COURSE_ID,
                title="Архитектура распределённых систем",
                description=(
                    "Курс о проектировании распределённых систем: границы сервисов, "
                    "согласованность данных, очереди сообщений и отказоустойчивость."
                ),
                teacher_id=SECOND_TEACHER_ID,
                status=models.CourseStatus.ACTIVE,
            )
            unit_of_work.repository.add(first_course)
            unit_of_work.repository.add(second_course)
            await unit_of_work.repository.flush()

            first_assignment = models.Assignment(
                id=ASSIGNMENT_ID,
                title="Лабораторная работа № 1",
                description="Каркас проекта, настройка окружения и тестов.",
                course_id=COURSE_ID,
                submit_limit=3,
                date_start=today,
                date_end=today + timedelta(days=14),
                materials_url="https://example.test/materials/lab-01.pdf",
            )
            second_assignment = models.Assignment(
                id=SECOND_ASSIGNMENT_ID,
                title="Лабораторная работа № 2",
                description="REST API, OpenAPI-контракт и обработка ошибок.",
                course_id=COURSE_ID,
                submit_limit=5,
                date_start=today,
                date_end=today + timedelta(days=21),
                materials_url="https://example.test/materials/lab-02.pdf",
            )
            third_assignment = models.Assignment(
                id=THIRD_ASSIGNMENT_ID,
                title="Курсовой проект",
                description="Проектирование и реализация распределённого сервиса.",
                course_id=SECOND_COURSE_ID,
                submit_limit=3,
                date_start=today,
                date_end=today + timedelta(days=60),
            )
            for assignment in (first_assignment, second_assignment, third_assignment):
                unit_of_work.repository.add(assignment)
            await unit_of_work.repository.flush()

            unit_of_work.repository.add(
                models.CourseStudent(course_id=COURSE_ID, student_id=STUDENT_ID)
            )
            unit_of_work.repository.add(
                models.CourseStudent(course_id=COURSE_ID, student_id=SECOND_STUDENT_ID)
            )
            unit_of_work.repository.add(
                models.CourseStudent(course_id=SECOND_COURSE_ID, student_id=SECOND_STUDENT_ID)
            )
            await unit_of_work.repository.flush()

            submission = models.Submission(
                id=SUBMISSION_ID,
                assignment_id=ASSIGNMENT_ID,
                student_id=STUDENT_ID,
                repository_url="https://git.example.test/student/course-work",
                artifacts_url="https://example.test/artifacts/course-work.zip",
                status=models.SubmissionStatus.SUBMITTED,
            )
            unit_of_work.repository.add(submission)
            await unit_of_work.repository.flush()

            review = models.Review(
                id=REVIEW_ID,
                submission_id=SUBMISSION_ID,
                reviewer_id=TEACHER_ID,
                type=models.ReviewType.MANUAL,
                feedback="Работа принята: структура проекта и тесты соответствуют требованиям.",
                mark=95.0,
                manual=95.0,
                status=models.ReviewStatus.COMPLETED,
            )
            unit_of_work.repository.add(review)
            submission.review_id = REVIEW_ID
            submission.status = models.SubmissionStatus.COMPLETED
            unit_of_work.repository.add(
                models.SubmissionAttemptCounter(
                    assignment_id=ASSIGNMENT_ID,
                    student_id=STUDENT_ID,
                    attempt_count=1,
                )
            )
            unit_of_work.repository.add(
                models.OutboxEvent(
                    id=OUTBOX_ID,
                    event_type="submission.created",
                    payload_json=json.dumps(
                        {
                            "submission_id": str(SUBMISSION_ID),
                            "assignment_id": str(ASSIGNMENT_ID),
                            "student_id": str(STUDENT_ID),
                        }
                    ),
                )
            )

        async with unit_of_work_factory.create() as unit_of_work:
            courses = await unit_of_work.courses.list_with_assignments(0, 10)
            for course in courses:
                print(f"{course.title}: заданий — {len(course.assignments)}")

        print("Демонстрационные данные созданы.")
        print(f"Курс 1: {COURSE_ID}")
        print(f"Курс 2: {SECOND_COURSE_ID}")
        print(f"Студент: {STUDENT_ID}")
        print()
        print("JWT для Postman/curl (действуют 8 часов):")
        print(f"admin:   {_token(settings, ADMIN_ID, 'admin')}")
        print(f"teacher: {_token(settings, TEACHER_ID, 'teacher')}")
        print(f"student: {_token(settings, STUDENT_ID, 'student')}")
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполняет базу демонстрационными данными.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Удалить существующие данные перед заполнением.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.reset))


if __name__ == "__main__":
    main()
