from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings


@pytest.fixture
def token_factory(settings: Settings):
    def make_token(role: str, user_id: UUID, expires_in: int = 3600) -> str:
        return jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "iss": settings.jwt.issuer,
                "aud": settings.jwt.audience,
                "exp": int(datetime.now(UTC).timestamp()) + expires_in,
            },
            settings.jwt.secret,
            algorithm=settings.jwt.algorithm,
        )

    return make_token


def test_course_assignment_submission_and_review_endpoints(
    app_client: TestClient, token_factory
) -> None:
    teacher_id = uuid4()
    admin_id = uuid4()
    student_id = uuid4()
    teacher = {"Authorization": f"Bearer {token_factory('teacher', teacher_id)}"}
    admin = {"Authorization": f"Bearer {token_factory('admin', admin_id)}"}
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    idempotency_key = str(uuid4())
    course_payload = {
        "title": "A sufficiently long course title",
        "description": "A course description that is long enough to satisfy the API contract.",
        "teacher_id": str(teacher_id),
        "status": "ACTIVE",
    }

    created_course = app_client.post(
        "/api/v1/courses",
        json=course_payload,
        headers={**admin, "Idempotency-Key": idempotency_key},
    )
    assert created_course.status_code == 201
    course = created_course.json()
    course_id = course["id"]
    assert (
        app_client.post(
            "/api/v1/courses",
            json=course_payload,
            headers={**admin, "Idempotency-Key": idempotency_key},
        ).json()
        == course
    )

    assert (
        app_client.post(
            "/api/v1/courses",
            json=course_payload,
            headers={**admin, "Idempotency-Key": idempotency_key},
        ).json()
        == course
    )

    assert app_client.get("/api/v1/courses", headers=student).json()["pagination"]["total"] == 0

    enrollment_key = str(uuid4())
    enrollment_headers = {**admin, "Idempotency-Key": enrollment_key}
    enrollment = app_client.post(
        f"/api/v1/courses/{course_id}/students/{student_id}",
        headers=enrollment_headers,
    )
    assert enrollment.status_code == 201
    assert (
        app_client.post(
            f"/api/v1/courses/{course_id}/students/{student_id}",
            headers=enrollment_headers,
        ).status_code
        == 201
    )
    assert app_client.get(f"/api/v1/courses/{course_id}/students", headers=admin).json()[
        "students_ids"
    ] == [str(student_id)]
    assert (
        app_client.patch(
            f"/api/v1/courses/{course_id}",
            json={"title": "Updated course title"},
            headers=teacher,
        ).status_code
        == 200
    )
    replacement = app_client.put(
        f"/api/v1/courses/{course_id}",
        json={
            "title": "Replaced course title",
            "description": "A description long enough to meet the sixty-four character course minimum.",
            "teacher_id": str(teacher_id),
            "status": "ACTIVE",
        },
        headers=admin,
    )
    assert replacement.status_code == 200

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
    assert (
        app_client.get(f"/api/v1/assignments/{assignment_id}", headers=student).status_code == 200
    )
    assert (
        app_client.patch(
            f"/api/v1/assignments/{assignment_id}",
            json={"title": "Updated assignment"},
            headers=teacher,
        ).status_code
        == 200
    )

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
    assert (
        app_client.get(f"/api/v1/submissions/{submission_id}", headers=student).status_code == 200
    )
    artifacts = app_client.get(f"/api/v1/submissions/{submission_id}/artifacts", headers=student)
    assert artifacts.status_code == 200
    assert artifacts.json()["data"][0]["submission_id"] == submission_id

    review_response = app_client.post(
        f"/api/v1/submissions/{submission_id}/review",
        json={"type": "AUTO", "mark": 91},
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    )
    assert review_response.status_code == 201
    assert review_response.json()["auto_score"] == 91
    assert (
        app_client.get(f"/api/v1/submissions/{submission_id}/review", headers=student).status_code
        == 200
    )
    assert (
        app_client.patch(
            f"/api/v1/submissions/{submission_id}/review",
            json={"mark": 96, "feedback": "Good work"},
            headers=teacher,
        ).status_code
        == 200
    )
    assert (
        app_client.get(f"/api/v1/submissions/{submission_id}/review", headers=student).json()[
            "mark"
        ]
        == 96
    )

    assert (
        app_client.delete(f"/api/v1/assignments/{assignment_id}", headers=teacher).status_code
        == 204
    )
    assert (
        app_client.delete(
            f"/api/v1/courses/{course_id}/students/{student_id}", headers=admin
        ).status_code
        == 204
    )
    assert app_client.delete(f"/api/v1/courses/{course_id}", headers=admin).status_code == 204


def test_auth_validation_and_pagination_contract(app_client: TestClient, token_factory) -> None:
    unauthorized = app_client.get("/api/v1/courses")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["content-type"].startswith("application/problem+json")
    assert unauthorized.json()["error"]["code"] == "TOKEN_MISSING"

    student_id = uuid4()
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    forbidden = app_client.post(
        "/api/v1/courses",
        json={"title": "A sufficiently long course title", "teacher_id": str(student_id)},
        headers={**student, "Idempotency-Key": str(uuid4())},
    )
    assert forbidden.status_code == 403

    invalid = app_client.get(
        "/api/v1/courses", headers={"Authorization": "Bearer invalid.token.value"}
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "TOKEN_INVALID"

    expired = app_client.get(
        "/api/v1/courses",
        headers={"Authorization": f"Bearer {token_factory('student', student_id, -60)}"},
    )
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "TOKEN_EXPIRED"
    assert app_client.get("/api/v1/courses?limit=101", headers=student).status_code == 422
    assert app_client.get("/api/v1/courses?offset=-1", headers=student).status_code == 422
    invalid_sort = app_client.get("/api/v1/courses?sort=missing_field:asc", headers=student)
    assert invalid_sort.status_code == 422

    error = app_client.get("/api/v1/courses/00000000-0000-0000-0000-000000000000", headers=student)
    assert error.status_code == 404
    assert error.json()["error"]["code"] == "COURSE_NOT_FOUND"


def test_course_and_assignment_access_is_scoped(app_client: TestClient, token_factory) -> None:
    teacher_id = uuid4()
    student_id = uuid4()
    outsider_id = uuid4()
    admin = {"Authorization": f"Bearer {token_factory('admin', uuid4())}"}
    teacher = {"Authorization": f"Bearer {token_factory('teacher', teacher_id)}"}
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    outsider = {"Authorization": f"Bearer {token_factory('student', outsider_id)}"}
    course = app_client.post(
        "/api/v1/courses",
        json={
            "title": "A sufficiently long course title",
            "description": "A description long enough to meet the sixty-four character course minimum.",
            "teacher_id": str(teacher_id),
        },
        headers={**admin, "Idempotency-Key": str(uuid4())},
    ).json()
    course_id = course["id"]
    assignment = app_client.post(
        "/api/v1/assignments",
        json={
            "title": "Assignment one",
            "course_id": course_id,
            "submit_limit": 3,
            "date_start": date.today().isoformat(),
            "date_end": (date.today() + timedelta(days=1)).isoformat(),
        },
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    ).json()

    assert app_client.get(f"/api/v1/courses/{course_id}", headers=outsider).status_code == 403
    assert (
        app_client.get(f"/api/v1/courses/{course_id}/students", headers=teacher).status_code == 200
    )
    outsider_teacher = {"Authorization": f"Bearer {token_factory('teacher', outsider_id)}"}
    assert (
        app_client.get(
            f"/api/v1/courses/{course_id}/students", headers=outsider_teacher
        ).status_code
        == 403
    )
    assert (
        app_client.get(f"/api/v1/assignments/{assignment['id']}", headers=outsider).status_code
        == 403
    )
    assert (
        app_client.get("/api/v1/assignments", headers=outsider).json()["pagination"]["total"] == 0
    )
    assert (
        app_client.post(
            "/api/v1/courses",
            json={
                "title": "A sufficiently long course title",
                "description": "A description long enough to meet the sixty-four character course minimum.",
                "teacher_id": str(teacher_id),
            },
            headers={**teacher, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )
    assert (
        app_client.post(
            f"/api/v1/courses/{course_id}/students/{student_id}",
            headers={**teacher, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )

    assert (
        app_client.post(
            f"/api/v1/courses/{course_id}/students/{student_id}",
            headers={**admin, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 201
    )
    assert app_client.get(f"/api/v1/courses/{course_id}", headers=student).status_code == 200
    assert (
        app_client.get(f"/api/v1/assignments/{assignment['id']}", headers=student).status_code
        == 200
    )

    forbidden_reassignment = app_client.patch(
        f"/api/v1/courses/{course_id}",
        json={"teacher_id": str(outsider_id)},
        headers=teacher,
    )
    assert forbidden_reassignment.status_code == 403


def test_submission_limit_enrollment_and_idempotency(app_client: TestClient, token_factory) -> None:
    teacher_id = uuid4()
    student_id = uuid4()
    admin = {"Authorization": f"Bearer {token_factory('admin', uuid4())}"}
    teacher = {"Authorization": f"Bearer {token_factory('teacher', teacher_id)}"}
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    course = app_client.post(
        "/api/v1/courses",
        json={
            "title": "A sufficiently long course title",
            "description": "A description long enough to meet the sixty-four character course minimum.",
            "teacher_id": str(teacher_id),
        },
        headers={**admin, "Idempotency-Key": str(uuid4())},
    ).json()
    app_client.post(
        f"/api/v1/courses/{course['id']}/students/{student_id}",
        headers={**admin, "Idempotency-Key": str(uuid4())},
    )
    assignment = app_client.post(
        "/api/v1/assignments",
        json={
            "title": "Assignment one",
            "course_id": course["id"],
            "submit_limit": 3,
            "date_start": date.today().isoformat(),
            "date_end": (date.today() + timedelta(days=2)).isoformat(),
        },
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    ).json()
    body = {"assignment_id": assignment["id"]}
    for _attempt_number in range(3):
        response = app_client.post(
            "/api/v1/submissions",
            json=body,
            headers={**student, "Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "SUBMITTED"
    limited = app_client.post(
        "/api/v1/submissions",
        json=body,
        headers={**student, "Idempotency-Key": str(uuid4())},
    )
    assert limited.status_code == 429

    future_assignment = app_client.post(
        "/api/v1/assignments",
        json={
            "title": "Future assignment",
            "course_id": course["id"],
            "submit_limit": 3,
            "date_start": (date.today() + timedelta(days=1)).isoformat(),
            "date_end": (date.today() + timedelta(days=3)).isoformat(),
        },
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    ).json()
    closed_submission = app_client.post(
        "/api/v1/submissions",
        json={"assignment_id": future_assignment["id"]},
        headers={**student, "Idempotency-Key": str(uuid4())},
    )
    assert closed_submission.status_code == 422

    outsider = {"Authorization": f"Bearer {token_factory('student', uuid4())}"}
    rejected = app_client.post(
        "/api/v1/submissions",
        json=body,
        headers={**outsider, "Idempotency-Key": str(uuid4())},
    )
    assert rejected.status_code == 403


def test_submission_attempt_limit_is_atomic(app_client: TestClient, token_factory) -> None:
    teacher_id = uuid4()
    student_id = uuid4()
    admin = {"Authorization": f"Bearer {token_factory('admin', uuid4())}"}
    teacher = {"Authorization": f"Bearer {token_factory('teacher', teacher_id)}"}
    student = {"Authorization": f"Bearer {token_factory('student', student_id)}"}
    course = app_client.post(
        "/api/v1/courses",
        json={
            "title": "A sufficiently long course title",
            "description": "A description long enough to meet the sixty-four character course minimum.",
            "teacher_id": str(teacher_id),
        },
        headers={**admin, "Idempotency-Key": str(uuid4())},
    ).json()
    app_client.post(
        f"/api/v1/courses/{course['id']}/students/{student_id}",
        headers={**admin, "Idempotency-Key": str(uuid4())},
    )
    assignment = app_client.post(
        "/api/v1/assignments",
        json={
            "title": "Assignment one",
            "course_id": course["id"],
            "submit_limit": 3,
            "date_start": date.today().isoformat(),
            "date_end": (date.today() + timedelta(days=1)).isoformat(),
        },
        headers={**teacher, "Idempotency-Key": str(uuid4())},
    ).json()
    submission_body = {"assignment_id": assignment["id"]}
    for _attempt_number in range(2):
        response = app_client.post(
            "/api/v1/submissions",
            json=submission_body,
            headers={**student, "Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201

    def submit_with_key(idempotency_key: UUID) -> int:
        response = app_client.post(
            "/api/v1/submissions",
            json=submission_body,
            headers={**student, "Idempotency-Key": str(idempotency_key)},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(submit_with_key, (uuid4(), uuid4())))
    assert sorted(statuses) == [201, 429]


def test_idempotency_key_is_scoped_to_actor_and_operation(
    app_client: TestClient, token_factory
) -> None:
    payload = {
        "title": "A sufficiently long course title",
        "description": "A description long enough to meet the sixty-four character course minimum.",
        "teacher_id": str(uuid4()),
    }
    shared_key = str(uuid4())
    admin_one = {"Authorization": f"Bearer {token_factory('admin', uuid4())}"}
    admin_two = {"Authorization": f"Bearer {token_factory('admin', uuid4())}"}
    first = app_client.post(
        "/api/v1/courses",
        json=payload,
        headers={**admin_one, "Idempotency-Key": shared_key},
    )
    second = app_client.post(
        "/api/v1/courses",
        json=payload,
        headers={**admin_two, "Idempotency-Key": shared_key},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]

    changed_payload = {**payload, "title": "A different sufficiently long title"}
    conflict = app_client.post(
        "/api/v1/courses",
        json=changed_payload,
        headers={**admin_one, "Idempotency-Key": shared_key},
    )
    assert conflict.status_code == 409
