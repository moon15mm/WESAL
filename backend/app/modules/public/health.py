from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
    try:
        import redis

        redis.Redis.from_url(settings.redis_url, socket_timeout=0.5).ping()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "unavailable"
    status = "ok" if checks["database"] == "ok" else "error"
    from fastapi.responses import JSONResponse

    return JSONResponse({"status": status, "checks": checks, "version": "1.0.0"}, status_code=200 if status == "ok" else 503)
