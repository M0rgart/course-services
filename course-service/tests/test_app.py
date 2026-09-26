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
    assert response.json() == response_json


def test_get_openapi(app_client: TestClient) -> None:
    response = app_client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json().get("openapi") == "3.1.0"


def test_get_swagger(app_client: TestClient) -> None:
    response = app_client.get("/docs")
    assert response.status_code == 200
    assert "<!DOCTYPE html>" in response.text