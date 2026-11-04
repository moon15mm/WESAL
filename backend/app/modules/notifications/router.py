from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Principal, current_principal
from app.core.errors import NotFound
from app.core.schemas import PageParams, paginate
from app.core.utils import utcnow
from app.integrations.channels import channel_enabled
from app.models.enums import Channel
from app.models.system import Notification, NotificationPreference, PushSubscription
from app.modules.notifications.service import EVENTS, render

router = APIRouter(prefix="/notifications", tags=["notifications"])


def out(n: Notification, locale: str) -> dict:
    title, body = render(n.event, locale, n.params or {})
    return {"id": str(n.id), "event": n.event, "params": n.params, "title": title, "body": body, "link": n.link,
            "entity_type": n.entity_type, "entity_id": n.entity_id, "read_at": n.read_at, "created_at": n.created_at}


@router.get("")
def list_notifications(unread: bool = False, params: PageParams = Depends(), db: Session = Depends(get_db),
                       principal: Principal = Depends(current_principal)):
    stmt = select(Notification).where(Notification.user_id == principal.id).order_by(Notification.created_at.desc())
    if unread:
        stmt = stmt.where(Notification.read_at.is_(None))
    page = paginate(db, stmt, params, lambda n: out(n, principal.locale))
    page["unread"] = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == principal.id, Notification.read_at.is_(None))) or 0
    return page


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    return {"unread": db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == principal.id, Notification.read_at.is_(None))) or 0}


@router.post("/{nid}/read")
def mark_read(nid: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    n = db.get(Notification, nid)
    if n is None or n.user_id != principal.id:
        raise NotFound()
    n.read_at = n.read_at or utcnow()
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def read_all(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    db.execute(update(Notification).where(Notification.user_id == principal.id, Notification.read_at.is_(None))
               .values(read_at=utcnow()))
    db.commit()
    return {"ok": True}


@router.get("/preferences")
def get_prefs(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    rows = db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == principal.id)).all()
    custom = {(r.event, r.channel.value): r.enabled for r in rows}
    channels = [c.value for c in Channel if c != Channel.in_app]
    return {"channels": {c: channel_enabled(c) for c in channels},
            "events": [{"event": e, "channels": {c: custom.get((e, c), Channel(c) in defaults) for c in channels}}
                       for e, defaults in EVENTS.items()]}


class PrefIn(BaseModel):
    event: str
    channel: Channel
    enabled: bool


@router.put("/preferences")
def set_prefs(data: list[PrefIn], db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    for p in data[:500]:
        if p.event not in EVENTS or p.channel == Channel.in_app:
            continue
        row = db.get(NotificationPreference, (principal.id, p.event, p.channel))
        if row is None:
            db.add(NotificationPreference(user_id=principal.id, event=p.event, channel=p.channel, enabled=p.enabled))
        else:
            row.enabled = p.enabled
    db.commit()
    return get_prefs(db, principal)


class PushIn(BaseModel):
    endpoint: str = Field(max_length=2000, pattern=r"^https://")
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


@router.get("/push/public-key")
def vapid_key():
    return {"enabled": channel_enabled("push"), "public_key": settings.vapid_public_key or None}


@router.post("/push/subscribe")
def push_subscribe(data: PushIn, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))
    if existing:
        existing.user_id, existing.p256dh, existing.auth = principal.id, data.p256dh, data.auth
    else:
        db.add(PushSubscription(user_id=principal.id, **data.model_dump()))
    db.commit()
    return {"ok": True}


@router.post("/push/unsubscribe")
def push_unsubscribe(data: PushIn, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint,
                                                        PushSubscription.user_id == principal.id))
    if existing:
        db.delete(existing)
        db.commit()
    return {"ok": True}
