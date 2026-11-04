from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.audit import audit
from app.core.db import get_db
from app.core.deps import Principal, current_principal
from app.core.errors import Conflict
from app.core.utils import utcnow
from app.models.enums import DataRequestKind, DataRequestStatus
from app.models.system import Advertisement, DataRequest
from app.modules.common import file_url
from app.modules.privacy.service import export_user_data

router = APIRouter(tags=["privacy"])


class DataRequestIn(BaseModel):
    kind: Literal["export", "deletion"]
    reason: str | None = Field(default=None, max_length=2000)


@router.get("/privacy/export")
def export_now(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    ratelimit.hit(f"export:{principal.id}", 5, 3600)
    audit(db, "privacy.export", actor_user_id=principal.id, request=request)
    db.commit()
    return JSONResponse(export_user_data(db, principal.user), headers={"Content-Disposition": 'attachment; filename="wesal-my-data.json"'})


@router.get("/privacy/requests")
def my_requests(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    rows = db.scalars(select(DataRequest).where(DataRequest.user_id == principal.id).order_by(DataRequest.created_at.desc())).all()
    return [{"id": str(r.id), "kind": r.kind.value, "status": r.status.value, "created_at": r.created_at, "notes": r.notes} for r in rows]


@router.post("/privacy/requests", status_code=201)
def create_request(data: DataRequestIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    open_req = db.scalar(select(DataRequest.id).where(DataRequest.user_id == principal.id, DataRequest.kind == DataRequestKind(data.kind),
                                                      DataRequest.status.in_([DataRequestStatus.pending, DataRequestStatus.processing])))
    if open_req:
        raise Conflict("request_exists")
    r = DataRequest(user_id=principal.id, kind=DataRequestKind(data.kind), reason=data.reason)
    db.add(r)
    audit(db, f"privacy.request_{data.kind}", actor_user_id=principal.id, entity_type="data_request", entity_id=r.id, request=request)
    db.commit()
    return {"id": str(r.id), "status": r.status.value}


@router.get("/ads")
def active_ads(placement: str, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    now = utcnow()
    rows = db.scalars(select(Advertisement).where(Advertisement.placement == placement, Advertisement.status == "active",
                                                  Advertisement.starts_at <= now, Advertisement.ends_at >= now).limit(5)).all()
    loc = principal.locale
    for a in rows:
        a.impressions += 1
    db.commit()
    return [{"id": str(a.id), "title": a.title.get(loc) or a.title.get("ar"), "body": (a.body or {}).get(loc) or (a.body or {}).get("ar"),
             "link_url": a.link_url, "image_url": file_url(a.image_file_id)} for a in rows]
