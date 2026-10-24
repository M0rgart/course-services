import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.config import get_settings
from src.core.db import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan_service_router(app: FastAPI) -> AsyncIterator[None]:
    logger.debug("Lifespan (service router) startup")
    yield
    logger.debug("Lifespan (service router) shutdown")


@asynccontextmanager
async def lifespan_app(app: FastAPI) -> AsyncIterator[None]:
    logger.debug("Lifespan (app) startup")
    settings = get_settings()
    if settings.db.url.startswith("sqlite"):
        db = app.state.db
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.debug("Lifespan (app) shutdown")