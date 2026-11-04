"""Returns: requested by the store, decided by the supplier. Settlement happens off-platform;
the original order is never deleted and commissions are adjusted once per return."""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import BusinessCtx, retailer_ctx, supplier_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.storage import save_upload
from app.core.utils import money, next_number, utcnow
from app.models.enums import FilePurpose, OrderStatus as S, ReturnStatus as R
from app.models.orders import Order, ReturnItem, ReturnRequest
from app.modules.commissions import service as commissions
from app.modules.common import file_url
from app.modules.notifications.service import members_with_permission, notify
from app.modules.orders import service as order_svc

router = APIRouter(tags=["returns"])

REASONS = ("damaged", "expired", "wrong_item", "quality", "excess", "other")


def return_out(r: ReturnRequest, order: Order | None = None, locale: str = "ar") -> dict:
    names = {i.id: (i.name_ar if locale == "ar" else i.name_en) for i in order.items} if order else {}
    return {"id": str(r.id), "number": r.number, "order_id": str(r.order_id), "order_number": order.number if order else None,
            "status": r.status.value, "reason": r.reason, "description": r.description, "total_value": r.total_value,
            "evidence": [file_url(uuid.UUID(f)) for f in r.evidence_file_ids], "decision_notes": r.decision_notes,
            "settlement_note": r.settlement_note, "decided_at": r.decided_at, "created_at": r.created_at,
            "items": [{"id": str(i.id), "order_item_id": str(i.order_item_id), "name": names.get(i.order_item_id),
                       "quantity": i.quantity, "approved_quantity": i.approved_quantity, "reason": i.reason} for i in r.items]}


@router.post("/retailer/orders/{oid}/returns", status_code=201)
async def request_return(oid: uuid.UUID, request: Request, reason: str = Form(...), description: str | None = Form(None),
                         items: str = Form(..., description='JSON: [{"order_item_id": "...", "quantity": 1}]'),
                         evidence: list[UploadFile] = File(default=[]), db: Session = Depends(get_db),
                         ctx: BusinessCtx = Depends(retailer_ctx("retailer.returns.manage"))):
    import json

    o = db.get(Order, oid)
    if o is None or o.retailer_id != ctx.business_id:
        raise NotFound()
    if o.status not in (S.delivered, S.completed, S.partially_returned):
        raise Conflict("order_not_returnable")
    ref = o.completed_at or o.delivered_at
    if ref and ref + timedelta(days=settings.return_window_days) < utcnow():
        raise Conflict("return_window_closed", params={"days": settings.return_window_days})
    if reason not in REASONS:
        raise ValidationFailed("invalid_reason")
    try:
        lines = json.loads(items)
        assert isinstance(lines, list) and lines
    except Exception:
        raise ValidationFailed("invalid_items")
    if len(evidence) > 5:
        raise ValidationFailed("too_many_files")
    by_id = {str(i.id): i for i in o.items}
    # quantities already under an open/approved return
    pending = {}
    for r in db.scalars(select(ReturnRequest).where(ReturnRequest.order_id == o.id,
                                                    ReturnRequest.status.in_([R.requested, R.approved, R.received]))):
        for ri in r.items:
            pending[str(ri.order_item_id)] = pending.get(str(ri.order_item_id), 0) + (ri.approved_quantity or ri.quantity)
    rr = ReturnRequest(number=next_number(db, "RET"), order_id=o.id, retailer_id=o.retailer_id, supplier_id=o.supplier_id,
                       requested_by=ctx.user.id, reason=reason, description=description, evidence_file_ids=[])
    total = 0
    for line in lines:
        it = by_id.get(str(line.get("order_item_id")))
        qty = int(line.get("quantity", 0))
        if it is None or qty <= 0:
            raise ValidationFailed("invalid_items")
        received = it.delivered_qty if it.delivered_qty is not None else it.quantity
        if qty + it.returned_qty + pending.get(str(it.id), 0) > received:
            raise ValidationFailed("return_exceeds_received", params={"product": it.name_ar})
        rr.items.append(ReturnItem(order_item_id=it.id, quantity=qty, reason=line.get("reason")))
        total += (it.line_total / it.quantity) * qty
    rr.total_value = money(total)
    for f in evidence:
        if f.filename:
            rec = save_upload(db, f, FilePurpose.return_evidence, owner_user_id=ctx.user.id, business_id=ctx.business_id)
            rr.evidence_file_ids = [*rr.evidence_file_ids, str(rec.id)]
    db.add(rr)
    db.flush()
    notify(db, members_with_permission(db, o.supplier_id, "supplier.returns.manage"), "return_requested",
           {"number": rr.number, "order": o.number, "retailer": o.retailer.trade_name_ar}, link=f"/app/supplier/returns/{rr.id}",
           entity_type="return", entity_id=rr.id)
    audit(db, "return.request", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="return",
          entity_id=rr.id, changes={"order": o.number, "lines": lines}, request=request)
    db.commit()
    return return_out(rr, o, ctx.principal.locale)


@router.get("/retailer/returns")
def retailer_returns(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.view"))):
    rows = db.scalars(select(ReturnRequest).where(ReturnRequest.retailer_id == ctx.business_id)
                      .order_by(ReturnRequest.created_at.desc()).limit(500)).all()
    return [return_out(r, db.get(Order, r.order_id), ctx.principal.locale) for r in rows]


@router.post("/retailer/returns/{rid}/cancel")
def retailer_cancel_return(rid: uuid.UUID, db: Session = Depends(get_db),
                           ctx: BusinessCtx = Depends(retailer_ctx("retailer.returns.manage"))):
    r = db.get(ReturnRequest, rid)
    if r is None or r.retailer_id != ctx.business_id:
        raise NotFound()
    if r.status != R.requested:
        raise Conflict("return_invalid_transition")
    r.status = R.cancelled
    db.commit()
    return return_out(r, db.get(Order, r.order_id), ctx.principal.locale)


@router.get("/supplier/returns")
def supplier_returns(status: R | None = None, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.view"))):
    stmt = select(ReturnRequest).where(ReturnRequest.supplier_id == ctx.business_id).order_by(ReturnRequest.created_at.desc())
    if status:
        stmt = stmt.where(ReturnRequest.status == status)
    return [return_out(r, db.get(Order, r.order_id), ctx.principal.locale) for r in db.scalars(stmt.limit(500))]


@router.get("/supplier/returns/{rid}")
def supplier_return(rid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.view"))):
    r = db.get(ReturnRequest, rid)
    if r is None or r.supplier_id != ctx.business_id:
        raise NotFound()
    return return_out(r, db.get(Order, r.order_id), ctx.principal.locale)


class DecisionLine(BaseModel):
    return_item_id: uuid.UUID
    approved_quantity: int = Field(ge=0)


class ReturnDecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=2000)
    items: list[DecisionLine] | None = None  # partial approval


class SettleIn(BaseModel):
    settlement_note: str = Field(min_length=3, max_length=2000)


def _sup_return(db, ctx, rid) -> ReturnRequest:
    r = db.get(ReturnRequest, rid)
    if r is None or r.supplier_id != ctx.business_id:
        raise NotFound()
    return r


@router.post("/supplier/returns/{rid}/decide")
def decide(rid: uuid.UUID, data: ReturnDecisionIn, request: Request, db: Session = Depends(get_db),
           ctx: BusinessCtx = Depends(supplier_ctx("supplier.returns.manage"))):
    r = _sup_return(db, ctx, rid)
    if r.status != R.requested:
        raise Conflict("return_invalid_transition")
    o = db.get(Order, r.order_id)
    r.decided_by, r.decided_at, r.decision_notes = ctx.user.id, utcnow(), data.notes
    if data.decision == "reject":
        r.status = R.rejected
    else:
        approved = {d.return_item_id: d.approved_quantity for d in (data.items or [])}
        total = 0
        by_item = {i.id: i for i in o.items}
        for ri in r.items:
            q = approved.get(ri.id, ri.quantity)
            if q > ri.quantity:
                raise ValidationFailed("approved_exceeds_requested")
            ri.approved_quantity = q
            it = by_item[ri.order_item_id]
            total += (it.line_total / it.quantity) * q
        r.total_value = money(total)
        r.status = R.approved
    notify(db, [r.requested_by], "return_decided", {"number": r.number, "decision": r.status.value},
           link=f"/app/store/orders/{o.id}", entity_type="return", entity_id=r.id)
    audit(db, "return.decide", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="return",
          entity_id=r.id, changes=data.model_dump(), request=request)
    db.commit()
    return return_out(r, o, ctx.principal.locale)


@router.post("/supplier/returns/{rid}/receive")
def receive(rid: uuid.UUID, request: Request, db: Session = Depends(get_db),
            ctx: BusinessCtx = Depends(supplier_ctx("supplier.returns.manage"))):
    """Goods physically received back: update returned quantities, order status, and commission (once)."""
    r = _sup_return(db, ctx, rid)
    if r.status != R.approved:
        raise Conflict("return_invalid_transition")
    o = db.get(Order, r.order_id)
    by_item = {i.id: i for i in o.items}
    for ri in r.items:
        it = by_item[ri.order_item_id]
        it.returned_qty += ri.approved_quantity or 0
    r.status = R.received
    fully = all(it.returned_qty >= (it.delivered_qty if it.delivered_qty is not None else it.quantity) for it in o.items)
    target = S.fully_returned if fully else S.partially_returned
    if o.status != target or target == S.partially_returned:
        if o.status == S.delivered:
            order_svc.transition(db, o, S.completed, ctx.user.id, "supplier", "completed before return")
            commissions.on_order_event(db, o, "completed")
        order_svc.transition(db, o, target, ctx.user.id, "supplier", f"return {r.number}")
    commissions.on_order_event(db, o, f"return:{r.id}")
    audit(db, "return.receive", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="return",
          entity_id=r.id, request=request)
    db.commit()
    return return_out(r, o, ctx.principal.locale)


@router.post("/supplier/returns/{rid}/settle")
def settle(rid: uuid.UUID, data: SettleIn, request: Request, db: Session = Depends(get_db),
           ctx: BusinessCtx = Depends(supplier_ctx("supplier.returns.manage"))):
    r = _sup_return(db, ctx, rid)
    if r.status != R.received:
        raise Conflict("return_invalid_transition")
    r.status, r.settlement_note = R.settled, data.settlement_note
    audit(db, "return.settle", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="return",
          entity_id=r.id, changes=data.model_dump(), request=request)
    db.commit()
    return return_out(r, db.get(Order, r.order_id), ctx.principal.locale)
