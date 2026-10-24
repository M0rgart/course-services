import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.config import Settings
from src.core.db import Database
from src.core.exceptions import DomainError
from src.web.middlewares import install_middlewares
from src.web.schemas import Error, ErrorDetail

logger = logging.getLogger(__name__)


def _error_response(
    request: Request, *, code: str, message: str, status: int
) -> JSONResponse:
    detail = ErrorDetail(
        code=code,
        message=message,
        status=status,
        path=str(request.url.path),
        request_id=getattr(
            request.state, "request_id", "00000000-0000-0000-0000-000000000000"
        ),
    )
    return JSONResponse(
        status_code=status, content=Error(error=detail).model_dump(mode="json")
    )


def _make_lifespan(user_lifespan):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: Settings = app.state.settings
        app.state.db = Database(settings)
        async with user_lifespan(app):
            try:
                yield
            finally:
                await app.state.db.dispose()

    return lifespan


def create_app(
    settings: Settings,
    routers: Iterable,
    user_lifespan,
    **params: Any,
) -> FastAPI:
    app_params = {**settings.app.model_dump(), **params}
    app = FastAPI(lifespan=_make_lifespan(user_lifespan), **app_params)
    app.state.settings = settings

    install_middlewares(app)

    @app.exception_handler(DomainError)
    async def _domain_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(
            request, code=exc.code, message=exc.message, status=exc.status
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "HTTP_ERROR")
        return _error_response(
            request, code=code, message=str(exc.detail), status=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request, code="VALIDATION_ERROR", message=str(exc.errors()), status=422
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return _error_response(
            request, code="INTERNAL_ERROR", message="Internal server error", status=500
        )

    for router in routers:
        app.include_router(router)
    return app