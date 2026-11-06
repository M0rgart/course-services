from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from src.core.config import Settings


@pytest.fixture
def token_factory(settings: Settings):
    def make_token(role: str, user_id: UUID) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "iss": settings.jwt.issuer,
                "aud": settings.jwt.audience,
                "exp": int(datetime.now(UTC).timestamp()) + 3600,
            },
            settings.jwt.secret,
            algorithm=settings.jwt.algorithm,
        )

    return make_token


def test_course_assignment_submission_and_review_endpoints(
    app_client: TestClient, token_factory
) -> None:
    teacher_id = uuid4()
    student_id = uuid4()
    teacher = {"Authorization": f"Bearer {token_factory('teacher', teacher_id)}"}
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    idempotency_key = str(uuid4())
    course_payload = {
        "title": "A sufficiently long course title",
        "description": "Course description",
        "teacher_id": str(teacher_id),
        "status": "ACTIVE",
    }

    created_course = app_client.post(
        "/api/v1/courses",
        json=course_payload,
        headers={**teacher, "Idempotency-Key": idempotency_key},
    )
    assert created_course.status_code == 201
    course = created_course.json()
    course_id = course["id"]
    assert app_client.post(
        "/api/v1/courses",
        json=course_payload,
        headers={**teacher, "Idempotency-Key": idempotency_key},
    ).json() == course

    assert app_client.get("/api/v1/courses", headers=student).json()["pagination"]["total"] == 1
    assert app_client.get(
        "/api/v1/courses?sort=created_at:desc", headers=student
    ).status_code == 200
    assert app_client.get(f"/api/v1/courses/{course_id}", headers=student).status_code == 200
    assert app_client.get(
        f"/api/v1/courses/{course_id}/students", headers=teacher
    ).json() == {"course_id": course_id, "students_ids": []}

    enrollment = app_client.post(
        f"/api/v1/courses/{course_id}/students/{student_id}", headers=teacher
    )
    assert enrollment.status_code == 201
    assert app_client.get(
        f"/api/v1/courses/{course_id}/students", headers=teacher
    ).json()["students_ids"] == [str(student_id)]

    assignment_payload = {
        "title": "Assignment one",
        "description": "Write a small project",
        "course_id": course_id,
        "submit_limit": 3,
        "date_start": date.today().isoformat(),
        "date_end": (date.today() + timedelta(days=7)).isoformat(),
        "materials_url": "https://example.test/materials",
    }
    assignment_response = app_client.post(
        "/api/v1/assignments",
        json=assignment_payload,
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    )
    assert assignment_response.status_code == 201
    assignment_id = assignment_response.json()["id"]
    assert app_client.get("/api/v1/assignments", headers=student).json()["pagination"]["total"] == 1
    assert app_client.get(
        f"/api/v1/assignments/{assignment_id}", headers=student
    ).status_code == 200
    assert app_client.patch(
        f"/api/v1/assignments/{assignment_id}",
        json={"title": "Updated assignment"},
        headers=teacher,
    ).status_code == 200

    submission_response = app_client.post(
        "/api/v1/submissions",
        json={
            "assignment_id": assignment_id,
            "repository_url": "https://git.example.test/course-work",
            "artifacts_url": "https://example.test/artifacts.zip",
        },
        headers={**student, "Idempotency-Key": str(uuid4())},
    )
    assert submission_response.status_code == 201
    submission_id = submission_response.json()["id"]
    assert app_client.get("/api/v1/submissions", headers=student).json()["pagination"]["total"] == 1
    assert app_client.get(f"/api/v1/submissions/{submission_id}", headers=student).status_code == 200
    artifacts = app_client.get(
        f"/api/v1/submissions/{submission_id}/artifacts", headers=student
    )
    assert artifacts.status_code == 200
    assert artifacts.json()["data"][0]["submission_id"] == submission_id

    review_response = app_client.post(
        f"/api/v1/submissions/{submission_id}/review",
        json={"type": "AUTO", "mark": 91},
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    )
    assert review_response.status_code == 201
    assert review_response.json()["auto_score"] == 91
    assert app_client.get(
        f"/api/v1/submissions/{submission_id}/review", headers=student
    ).status_code == 200
    assert app_client.patch(
        f"/api/v1/submissions/{submission_id}/review",
        json={"mark": 96, "feedback": "Good work"},
        headers=teacher,
    ).status_code == 200
    assert app_client.get(
        f"/api/v1/submissions/{submission_id}/review", headers=student
    ).json()["mark"] == 96

    assert app_client.delete(
        f"/api/v1/assignments/{assignment_id}", headers=teacher
    ).status_code == 204
    assert app_client.delete(
        f"/api/v1/courses/{course_id}/students/{student_id}", headers=teacher
    ).status_code == 204
    assert app_client.delete(f"/api/v1/courses/{course_id}", headers=teacher).status_code == 204


def test_auth_validation_and_pagination_contract(
    app_client: TestClient, token_factory
) -> None:
    unauthorized = app_client.get("/api/v1/courses")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["content-type"].startswith("application/problem+json")

    student_id = uuid4()
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    forbidden = app_client.post(
        "/api/v1/courses",
        json={"title": "A sufficiently long course title", "teacher_id": str(student_id)},
        headers={**student, "Idempotency-Key": str(uuid4())},
    )
    assert forbidden.status_code == 403
    assert app_client.get("/api/v1/courses?limit=101", headers=student).status_code == 422
    assert app_client.get("/api/v1/courses?offset=-1", headers=student).status_code == 422
    invalid_sort = app_client.get("/api/v1/courses?sort=missing_field:asc", headers=student)
    assert invalid_sort.status_code == 422

    error = app_client.get("/api/v1/courses/00000000-0000-0000-0000-000000000000", headers=student)
    assert error.status_code == 404
    assert error.json()["error"]["code"] == "COURSE_NOT_FOUND"
