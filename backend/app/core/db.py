"""Database engine, session factory and row-level-security context propagation.

Tenant isolation is enforced twice:
1. In application services (every query is scoped to the caller's businesses).
2. In PostgreSQL row-level security policies (defense in depth). The runtime role
   `wesal_app` is not the table owner and policies are FORCED, so a missing
   filter in application code cannot leak another tenant's rows.

The RLS context is stored in ``Session.info["rls"]`` and re-applied with
``set_config(..., is_local => true)`` at the start of every transaction.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy import DateTime, MetaData, create_engine, event, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _apply_rls(session: Session, connection) -> None:
    ctx = session.info.get("rls")
    if not ctx:
        ctx = {"bypass": False, "user_id": "", "business_ids": "", "rep_id": ""}
    connection.execute(
        text(
            "SELECT set_config('wesal.bypass', :bypass, true),"
            " set_config('wesal.user_id', :uid, true),"
            " set_config('wesal.business_ids', :bids, true),"
            " set_config('wesal.rep_id', :rid, true)"
        ),
        {
            "bypass": "on" if ctx.get("bypass") else "off",
            "uid": ctx.get("user_id") or "",
            "bids": ctx.get("business_ids") or "",
            "rid": ctx.get("rep_id") or "",
        },
    )


@event.listens_for(Session, "after_begin")
def _after_begin(session: Session, transaction, connection) -> None:  # noqa: ARG001
    _apply_rls(session, connection)


def set_rls_context(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    business_ids: list[uuid.UUID] | None = None,
    rep_id: uuid.UUID | None = None,
    bypass: bool = False,
) -> None:
    db.info["rls"] = {
        "bypass": bypass,
        "user_id": str(user_id) if user_id else "",
        "business_ids": ",".join(str(b) for b in (business_ids or [])),
        "rep_id": str(rep_id) if rep_id else "",
    }
    if db.in_transaction():
        _apply_rls(db, db.connection())


@contextmanager
def system_context(db: Session) -> Iterator[Session]:
    """Temporarily lift RLS for trusted, server-side side effects
    (e.g. creating a commission row for a representative when a retailer approves).
    Never wrap code that takes identifiers from user input without authorization checks."""
    previous = dict(db.info.get("rls") or {})
    ctx = dict(previous)
    ctx["bypass"] = True
    db.info["rls"] = ctx
    if db.in_transaction():
        _apply_rls(db, db.connection())
    try:
        yield db
        db.flush()  # writes made in the privileged context must hit the DB before RLS is restored
    finally:
        db.info["rls"] = previous
        if db.in_transaction():
            _apply_rls(db, db.connection())


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def system_session() -> Iterator[Session]:
    """Session for workers / scripts with RLS bypass."""
    db = SessionLocal()
    db.info["rls"] = {"bypass": True}
    try:
        yield db
    finally:
        db.close()
