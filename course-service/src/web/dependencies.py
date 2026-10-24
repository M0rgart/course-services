from dataclasses import dataclass
from typing import Annotated

from fastapi import Header

from src.web.schemas import Pagination


@dataclass(frozen=True)
class Page:
    offset: int
    limit: int

    def apply(self, items: list) -> list:
        return items[self.offset : self.offset + self.limit]

    def pagination(self, total: int) -> Pagination:
        return Pagination(offset=self.offset, limit=self.limit, total=total)


def get_page(offset: int = 0, limit: int = 10) -> Page:
    if offset < 0:
        offset = 0
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    return Page(offset=offset, limit=limit)


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=36, max_length=36)]