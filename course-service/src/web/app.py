import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.config import Settings, get_settings
from src.core.db import Database
from src.core.exceptions import DomainError
from src.core.external import AsyncExternalService
from src.infrastructure.outbox import LoggingEventPublisher, OutboxDispatcher
from src.infrastructure.unit_of_work import SqlAlchemyUnitOfWorkFactory
from src.web.middlewares import install_middlewares
from src.web.schemas import Error, ErrorDetail

logger = logging.getLogger(__name__)
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def _error_response(request: Request, *, code: str, message: str, status: int) -> JSONResponse:
    detail = ErrorDetail(
        code=code,
        message=message,
        status=status,
        path=str(request.url.path),
        request_id=getattr(request.state, "request_id", UUID(int=0)),
    )
    return JSONResponse(
        status_code=status,
        content=Error(error=detail).model_dump(mode="json"),
        media_type="application/problem+json",
    )


def _make_lifespan(user_lifespan: Lifespan) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: Settings = app.state.settings
        app.state.db = Database(settings)
        app.state.external_service = AsyncExternalService(settings.external)
        app.state.uow_factory = SqlAlchemyUnitOfWorkFactory(app.state.db.session_factory)
        try:
            async with user_lifespan(app):
                stop_event = asyncio.Event()
                dispatcher = OutboxDispatcher(app.state.uow_factory, LoggingEventPublisher())
                outbox_task = asyncio.create_task(dispatcher.run(stop_event))
                try:
                    yield
                finally:
                    stop_event.set()
                    await outbox_task
        finally:
            await app.state.db.dispose()

    return lifespan


def create_app(
    settings: Settings,
    routers: Iterable[APIRouter],
    user_lifespan: Lifespan,
    **params: Any,
) -> FastAPI:
    app_params = {**settings.app.model_dump(), **params}
    app = FastAPI(lifespan=_make_lifespan(user_lifespan), **app_params)
    app.state.settings = settings
    app.dependency_overrides[get_settings] = lambda: settings

    install_middlewares(app, settings)

    @app.exception_handler(DomainError)
    async def _domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(request, code=exc.code, message=exc.message, status=exc.status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "HTTP_ERROR")
        return _error_response(request, code=code, message=str(exc.detail), status=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            request,
            code="VALIDATION_ERROR",
            message="Ошибка валидации запроса",
            status=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, _exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _error_response(
            request, code="INTERNAL_ERROR", message="Internal server error", status=500
        )

    for router in routers:
        app.include_router(router)
    return app
