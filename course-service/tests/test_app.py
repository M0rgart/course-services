import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "url_path,status,response_json",
    (
        ("/", 404, {"detail": "Not Found"}),
        ("/service", 200, {"healthy": True}),
    ),
)
def test_get(
    app_client: TestClient,
    url_path: str,
    status: int,
    response_json: dict,
) -> None:
    response = app_client.get(url_path)
    assert response.status_code == status
    if status == 404:
        error = response.json()["error"]
        assert error["code"] == "NOT_FOUND"
        assert error["message"] == "Not Found"
        assert error["status"] == 404
        assert error["path"] == url_path
        assert error["request_id"]
        assert response.headers["content-type"].startswith("application/problem+json")
    else:
        assert response.json() == response_json


def test_get_openapi(app_client: TestClient) -> None:
    response = app_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json().get("openapi") == "3.1.0"


def test_get_swagger(app_client: TestClient) -> None:
    response = app_client.get("/docs")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text


def test_request_id_and_security_headers(app_client: TestClient) -> None:
    request_id = "d90cd8eb-23d0-40d4-903a-d2dba4da9d87"
    response = app_client.get("/service", headers={"X-Request-Id": request_id})

    assert response.headers["X-Request-Id"] == request_id
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_invalid_request_id_is_replaced(app_client: TestClient) -> None:
    response = app_client.get("/service", headers={"X-Request-Id": "not-a-uuid"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] != "not-a-uuid"


def test_oversized_request_is_rejected(app_client: TestClient) -> None:
    response = app_client.post(
        "/service", headers={"Content-Length": str(1_048_577)}, content=b""
    )

    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error"]["code"] == "BODY_TOO_LARGE"
