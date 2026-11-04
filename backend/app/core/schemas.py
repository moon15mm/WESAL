from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1, le=100000), page_size: int = Query(20, ge=1, le=100)):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginate(db, stmt, params: PageParams, mapper=None):
    from sqlalchemy import func, select

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.limit(params.page_size).offset(params.offset)).unique().all()
    items = [mapper(r) for r in rows] if mapper else rows
    return {"items": items, "total": total or 0, "page": params.page, "page_size": params.page_size}


class Msg(BaseModel):
    ok: bool = True
    message: str | None = None
