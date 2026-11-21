from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import Depends, Header, Query, Request

from src.application.ports import Repository, UnitOfWork
from src.core.db import get_repository, get_uow
from src.core.external import AsyncExternalService
from src.web.schemas import Pagination


@dataclass(frozen=True)
class Page:
    offset: int
    limit: int

    def apply(self, items: list[Any]) -> list[Any]:
        return items[self.offset : self.offset + self.limit]

    def pagination(self, total: int) -> Pagination:
        return Pagination(offset=self.offset, limit=self.limit, total=total)


def get_page(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> Page:
    return Page(offset=offset, limit=limit)


IdempotencyKey = Annotated[UUID, Header(alias="Idempotency-Key")]


def get_external_service(request: Request) -> AsyncExternalService:
    return cast(AsyncExternalService, request.app.state.external_service)


ExternalServiceDep = Annotated[AsyncExternalService, Depends(get_external_service)]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_uow)]
RepositoryDep = Annotated[Repository, Depends(get_repository)]
