import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import Settings, get_settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app
from src.web.routers import service_router


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings, (service_router,), lifespan=lifespan_app)


@pytest.fixture
def app_client(app: FastAPI) -> TestClient:
    return TestClient(app)