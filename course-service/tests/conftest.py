from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import DatabaseSettings, JWTSettings, Settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = (tmp_path / "test.db").as_posix()
    return Settings(
        db=DatabaseSettings(url=f"sqlite+aiosqlite:///{database_path}"),
        jwt=JWTSettings(secret=f"{uuid4().hex}{uuid4().hex}"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    from src.web.routers import all_routers

    return create_app(settings, all_routers, user_lifespan=lifespan_app)


@pytest.fixture
def app_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
