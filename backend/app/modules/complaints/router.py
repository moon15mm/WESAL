"""Complaints & order disputes with a message thread. Platform admins mediate."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import Principal, current_principal
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.utils import next_number
from app.models.business import Business
from app.models.enums import BusinessType, ComplaintCategory, ComplaintKind, ComplaintStatus as CS, OrderStatus, Priority
from app.models.identity import Role, UserRole
from app.models.orders import Order
from app.models.reps import Representative
from app.models.system import Complaint, ComplaintMessage
from app.modules.commissions import service as commissions
from app.modules.common import business_brief
from app.modules.notifications.service import members_with_permission, notify
from app.modules.orders import service as order_svc

router = APIRouter(tags=["complaints"])

DISPUTABLE = {OrderStatus.delivered, OrderStatus.completed, OrderStatus.partially_returned}


class ComplaintIn(BaseModel):
    kind: ComplaintKind = ComplaintKind.complaint
    category: ComplaintCategory
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=8000)
    order_id: uuid.UUID | None = None
    against_business_id: uuid.UUID | None = None
    against_representative_id: uuid.UUID | None = None
    business_id: uuid.UUID | None = None  # complainant business context (must be a member)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


def _side(c: Complaint, p: Principal) -> str | None:
    bids = set(p.business_ids())
    if c.raised_by_user_id == p.id or (c.raised_by_business_id and c.raised_by_business_id in bids):
        return "complainant"
    if (c.against_business_id and c.against_business_id in bids) or (p.rep and c.against_representative_id == p.rep.id):
        return "respondent"
    return None


def complaint_out(db: Session, c: Complaint, locale: str, side: str | None) -> dict:
    with system_context(db):
        raised = db.get(Business, c.raised_by_business_id) if c.raised_by_business_id else None
        against = db.get(Business, c.against_business_id) if c.against_business_id else None
        rep = db.get(Representative, c.against_representative_id) if c.against_representative_id else None
        order = db.get(Order, c.order_id) if c.order_id else None
    return {"id": str(c.id), "number": c.number, "kind": c.kind.value, "category": c.category.value, "status": c.status.value,
            "priority": c.priority.value, "subject": c.subject, "description": c.description,
            "order": {"id": str(order.id), "number": order.number, "status": order.status.value} if order else None,
            "raised_by_business": business_brief(raised, locale), "against_business": business_brief(against, locale),
            "against_representative": {"id": str(rep.id), "display_name": rep.display_name} if rep else None,
            "resolution": c.resolution, "resolved_at": c.resolved_at, "created_at": c.created_at, "updated_at": c.updated_at,
            "my_side": side,
            "messages": [{"id": str(m.id), "author_side": m.author_side, "body": m.body, "created_at": m.created_at}
                         for m in c.messages if not m.internal or side == "admin"]}


def _admins(db: Session) -> list[uuid.UUID]:
    return list(db.scalars(select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
        Role.code.in_(["platform_admin", "platform_support"]))))


@router.post("/complaints", status_code=201)
def create(data: ComplaintIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    bids = set(principal.business_ids())
    raised_business = None
    if data.business_id:
        if data.business_id not in bids:
            raise Forbidden("not_a_member")
        raised_business = data.business_id
    elif len(bids) == 1:
        raised_business = next(iter(bids))
    against_b, against_r = data.against_business_id, data.against_representative_id
    order = None
    if data.order_id:
        with system_context(db):
            order = db.get(Order, data.order_id)
        rep_id = principal.rep.id if principal.rep else None
        if order is None or not (order.retailer_id in bids or order.supplier_id in bids or (rep_id and order.representative_id == rep_id)):
            raise NotFound()
        if raised_business is None or raised_business not in (order.retailer_id, order.supplier_id):
            raised_business = order.retailer_id if order.retailer_id in bids else (order.supplier_id if order.supplier_id in bids else None)
        if against_b is None and against_r is None:
            against_b = order.supplier_id if raised_business == order.retailer_id else order.retailer_id
    if data.kind == ComplaintKind.order_dispute:
        if order is None:
            raise ValidationFailed("order_required")
        if raised_business != order.retailer_id:
            raise Forbidden("only_store_can_dispute")
        if order.status not in DISPUTABLE:
            raise Conflict("order_not_disputable")
    if against_b and against_b in bids:
        raise ValidationFailed("cannot_complain_about_self")
    c = Complaint(number=next_number(db, "CMP"), kind=data.kind, category=data.category, subject=data.subject,
                  description=data.description, order_id=order.id if order else None, raised_by_user_id=principal.id,
                  raised_by_business_id=raised_business, against_business_id=against_b, against_representative_id=against_r,
                  priority=Priority.high if data.kind == ComplaintKind.order_dispute else Priority.normal)
    db.add(c)
    db.flush()
    if data.kind == ComplaintKind.order_dispute:
        with system_context(db):
            c.order_status_before = order.status.value
            order_svc.transition(db, order, OrderStatus.disputed, principal.id, "retailer", data.subject)
            commissions.on_order_event(db, order, "disputed")
    recipients = _admins(db)
    if against_b:
        recipients += members_with_permission(db, against_b)
    if against_r:
        with system_context(db):
            rep = db.get(Representative, against_r)
        if rep:
            recipients.append(rep.user_id)
    notify(db, recipients, "complaint_new", {"number": c.number, "subject": c.subject}, link=f"/app/complaints/{c.id}",
           entity_type="complaint", entity_id=c.id)
    audit(db, "complaint.create", actor_user_id=principal.id, actor_business_id=raised_business, entity_type="complaint",
          entity_id=c.id, changes={"kind": data.kind.value, "order": str(data.order_id) if data.order_id else None}, request=request)
    db.commit()
    db.refresh(c)
    return complaint_out(db, c, principal.locale, "complainant")


@router.get("/complaints")
def mine(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    bids = principal.business_ids()
    conds = [Complaint.raised_by_user_id == principal.id]
    if bids:
        conds += [Complaint.raised_by_business_id.in_(bids), Complaint.against_business_id.in_(bids)]
    if principal.rep:
        conds.append(Complaint.against_representative_id == principal.rep.id)
    rows = db.scalars(select(Complaint).where(or_(*conds)).order_by(Complaint.created_at.desc()).limit(300)).all()
    return [complaint_out(db, c, principal.locale, _side(c, principal)) for c in rows]


@router.get("/complaints/{cid}")
def get_one(cid: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    c = db.get(Complaint, cid)
    if c is None or _side(c, principal) is None:
        raise NotFound()
    return complaint_out(db, c, principal.locale, _side(c, principal))


@router.post("/complaints/{cid}/messages", status_code=201)
def reply(cid: uuid.UUID, data: MessageIn, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    c = db.get(Complaint, cid)
    side = _side(c, principal) if c else None
    if c is None or side is None:
        raise NotFound()
    if c.status in (CS.closed, CS.rejected):
        raise Conflict("complaint_closed")
    db.add(ComplaintMessage(complaint_id=c.id, author_user_id=principal.id, author_side=side, body=data.body))
    if side == "respondent" and c.status == CS.awaiting_response:
        c.status = CS.in_review
    notify(db, [c.raised_by_user_id] if side == "respondent" else _admins(db), "complaint_reply", {"number": c.number},
           link=f"/app/complaints/{c.id}", entity_type="complaint", entity_id=c.id, exclude_user_id=principal.id)
    db.commit()
    db.refresh(c)
    return complaint_out(db, c, principal.locale, side)


__all__ = ["router", "BusinessType"]
