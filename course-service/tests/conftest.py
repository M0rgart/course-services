import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.core.config import Settings, get_settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    configured = get_settings()
    database_path = (tmp_path / "test.db").as_posix()
    return configured.model_copy(
        update={
            "db": configured.db.model_copy(
                update={"url": f"sqlite+aiosqlite:///{database_path}"}
            )
        }
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    from src.web.routers import all_routers

    return create_app(settings, all_routers, user_lifespan=lifespan_app)


@pytest.fixture
def app_client(app: FastAPI):
    with TestClient(app) as client:
        yield client
