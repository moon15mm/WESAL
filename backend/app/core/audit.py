"""Audit logging. Rows are append-only (DB trigger + revoked privileges)."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models.system import AuditLog

log = logging.getLogger("wesal.audit")

SENSITIVE_KEYS = {"password", "password_hash", "token", "code", "secret", "mfa_secret_enc", "otp", "national_id"}


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in SENSITIVE_KEYS else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value") and not isinstance(value, (str, int, float)):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def audit(
    db: Session,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    actor_business_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: Any = None,
    changes: dict | None = None,
    reason: str | None = None,
    result: str = "success",
    request=None,
) -> None:
    """Add an audit row to the current transaction (committed with the business change)."""
    ip = ua = rid = None
    if request is not None:
        ip = getattr(request.state, "client_ip", None)
        ua = (request.headers.get("user-agent") or "")[:400]
        rid = getattr(request.state, "request_id", None)
    # Core INSERT without RETURNING: the runtime role may append but not read audit rows (RLS).
    db.execute(
        insert(AuditLog).values(
            action=action,
            actor_user_id=actor_user_id,
            actor_business_id=actor_business_id,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            changes=_scrub(changes) if changes else None,
            reason=reason,
            result=result,
            ip=ip,
            user_agent=ua,
            request_id=rid,
        )
    )


def audit_denied(action: str, *, actor_user_id=None, entity_type=None, entity_id=None, reason=None, request=None) -> None:
    """Record a denied access attempt in an independent transaction (survives the request rollback)."""
    db = SessionLocal()
    try:
        audit(db, action, actor_user_id=actor_user_id, entity_type=entity_type, entity_id=entity_id,
              reason=reason, result="denied", request=request)
        db.commit()
    except Exception:  # pragma: no cover - audit must never break the request
        log.exception("failed to write denied-access audit row")
        db.rollback()
    finally:
        db.close()
