from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, Header, Query, Request

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


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=36, max_length=36)]


def get_external_service(request: Request) -> AsyncExternalService:
    return cast(AsyncExternalService, request.app.state.external_service)


ExternalServiceDep = Annotated[
    AsyncExternalService, Depends(get_external_service)
]
