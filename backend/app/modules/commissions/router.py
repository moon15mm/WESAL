"""Commissions: representative view & disputes, supplier approval, payouts and adjustments."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, supplier_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.schemas import PageParams, paginate
from app.core.storage import save_upload
from app.core.utils import money, utcnow
from app.models.business import Business
from app.models.commissions import Commission, CommissionAdjustment, CommissionDispute, CommissionPayment
from app.models.enums import CommissionStatus as CS
from app.models.enums import DisputeStatus, FilePurpose
from app.models.orders import Order
from app.models.reps import Representative
from app.modules.common import business_brief, file_url
from app.modules.notifications.service import members_with_permission, notify

router = APIRouter(tags=["commissions"])


def commission_out(db: Session, c: Commission, locale: str) -> dict:
    with system_context(db):
        o = db.get(Order, c.order_id)
        sup = db.get(Business, c.supplier_id)
        rep = db.get(Representative, c.representative_id)
        disputes = db.scalars(select(CommissionDispute).where(CommissionDispute.commission_id == c.id)).all()
    return {"id": str(c.id), "status": c.status.value, "amount": c.amount, "original_amount": c.original_amount,
            "eligible_amount": c.eligible_amount, "currency": c.currency, "breakdown": c.breakdown, "due_at": c.due_at,
            "approved_at": c.approved_at, "paid_at": c.paid_at, "status_reason": c.status_reason, "created_at": c.created_at,
            "order": {"id": str(o.id), "number": o.number, "status": o.status.value, "total": o.total,
                      "retailer": o.retailer.trade_name_ar} if o else None,
            "supplier": business_brief(sup, locale),
            "representative": {"id": str(rep.id), "display_name": rep.display_name} if rep else None,
            "authorization_id": str(c.authorization_id),
            "adjustments": [{"amount_delta": a.amount_delta, "reason": a.reason, "note": a.note, "created_at": a.created_at}
                            for a in c.adjustments],
            "disputes": [{"id": str(d.id), "status": d.status.value, "reason": d.reason, "expected_amount": d.expected_amount,
                          "resolution": d.resolution, "resolved_amount": d.resolved_amount, "created_at": d.created_at}
                         for d in disputes]}


def _summary(db: Session, where) -> dict:
    rows = db.execute(select(Commission.status, func.count(), func.coalesce(func.sum(Commission.amount), 0))
                      .where(where).group_by(Commission.status)).all()
    return {s.value: {"count": n, "amount": money(a)} for s, n, a in rows}


# ------------------------------------------------------------------ representative
@router.get("/rep/commissions")
def rep_list(status: CS | None = None, supplier_id: uuid.UUID | None = None, params: PageParams = Depends(),
             db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    stmt = select(Commission).where(Commission.representative_id == ctx.rep.id).order_by(Commission.created_at.desc())
    if status:
        stmt = stmt.where(Commission.status == status)
    if supplier_id:
        stmt = stmt.where(Commission.supplier_id == supplier_id)
    page = paginate(db, stmt, params, lambda c: commission_out(db, c, ctx.principal.locale))
    page["summary"] = _summary(db, Commission.representative_id == ctx.rep.id)
    return page


class DisputeIn(BaseModel):
    reason: str = Field(min_length=10, max_length=4000)
    expected_amount: Decimal | None = Field(default=None, ge=0)


@router.post("/rep/commissions/{cid}/dispute", status_code=201)
def rep_dispute(cid: uuid.UUID, data: DisputeIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    c = db.get(Commission, cid)
    if c is None or c.representative_id != ctx.rep.id:
        raise NotFound()
    if c.status in (CS.cancelled, CS.disputed):
        raise Conflict("commission_not_disputable")
    if db.scalar(select(CommissionDispute.id).where(CommissionDispute.commission_id == c.id,
                                                    CommissionDispute.status.in_([DisputeStatus.open, DisputeStatus.in_review]))):
        raise Conflict("dispute_exists")
    d = CommissionDispute(commission_id=c.id, raised_by=ctx.user.id, reason=data.reason, expected_amount=data.expected_amount,
                          previous_status=c.status.value)
    db.add(d)
    c.status = CS.disputed
    notify(db, members_with_permission(db, c.supplier_id, "supplier.commissions.manage"), "dispute_new",
           {"representative": ctx.rep.display_name, "amount": str(c.amount)}, link="/app/supplier/commissions",
           entity_type="commission", entity_id=c.id)
    audit(db, "commission.dispute", actor_user_id=ctx.user.id, entity_type="commission", entity_id=c.id,
          changes=data.model_dump(), request=request)
    db.commit()
    return commission_out(db, c, ctx.principal.locale)


@router.get("/rep/commission-payments")
def rep_payments(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rows = db.scalars(select(CommissionPayment).where(CommissionPayment.representative_id == ctx.rep.id)
                      .order_by(CommissionPayment.paid_at.desc())).all()
    return [payment_out(p) for p in rows]


@router.post("/rep/commission-payments/{pid}/acknowledge")
def rep_ack(pid: uuid.UUID, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    p = db.get(CommissionPayment, pid)
    if p is None or p.representative_id != ctx.rep.id:
        raise NotFound()
    p.acknowledged_at = p.acknowledged_at or utcnow()
    db.commit()
    return payment_out(p)


def payment_out(p: CommissionPayment) -> dict:
    return {"id": str(p.id), "supplier_id": str(p.supplier_id), "representative_id": str(p.representative_id),
            "amount": p.amount, "commission_ids": p.commission_ids, "method": p.method, "reference": p.reference,
            "proof_url": file_url(p.proof_file_id), "paid_at": p.paid_at, "acknowledged_at": p.acknowledged_at}


# ------------------------------------------------------------------ supplier
@router.get("/supplier/commissions")
def supplier_list(status: CS | None = None, representative_id: uuid.UUID | None = None, params: PageParams = Depends(),
                  db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.view"))):
    stmt = select(Commission).where(Commission.supplier_id == ctx.business_id).order_by(Commission.created_at.desc())
    if status:
        stmt = stmt.where(Commission.status == status)
    if representative_id:
        stmt = stmt.where(Commission.representative_id == representative_id)
    page = paginate(db, stmt, params, lambda c: commission_out(db, c, ctx.principal.locale))
    page["summary"] = _summary(db, Commission.supplier_id == ctx.business_id)
    return page


class IdsIn(BaseModel):
    commission_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


@router.post("/supplier/commissions/approve")
def approve(data: IdsIn, request: Request, db: Session = Depends(get_db),
            ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    rows = db.scalars(select(Commission).where(Commission.id.in_(data.commission_ids), Commission.supplier_id == ctx.business_id)).all()
    if len(rows) != len(set(data.commission_ids)):
        raise NotFound()
    for c in rows:
        if c.status != CS.due:
            raise Conflict("commission_not_due", params={"id": str(c.id), "status": c.status.value})
        c.status, c.approved_at, c.approved_by = CS.approved, utcnow(), ctx.user.id
    audit(db, "commission.approve", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          changes={"ids": [str(c.id) for c in rows]}, request=request)
    db.commit()
    return {"approved": len(rows)}


@router.post("/supplier/commission-payments", status_code=201)
def record_payment(request: Request, commission_ids: str = Form(..., description="comma separated ids"),
                   method: str = Form(..., max_length=30), reference: str | None = Form(None, max_length=120),
                   proof: UploadFile | None = File(None), db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    """Record an off-platform payout for approved commissions of ONE representative."""
    try:
        ids = [uuid.UUID(x.strip()) for x in commission_ids.split(",") if x.strip()]
    except ValueError:
        raise ValidationFailed("invalid_ids")
    if not ids or method not in ("bank_transfer", "cash", "cheque", "other"):
        raise ValidationFailed("invalid_payment")
    rows = db.scalars(select(Commission).where(Commission.id.in_(ids), Commission.supplier_id == ctx.business_id)
                      .with_for_update()).all()
    if len(rows) != len(set(ids)):
        raise NotFound()
    reps = {c.representative_id for c in rows}
    if len(reps) != 1:
        raise ValidationFailed("single_representative_required")
    for c in rows:
        if c.status != CS.approved:
            raise Conflict("commission_not_approved", params={"id": str(c.id)})
    proof_id = save_upload(db, proof, FilePurpose.payment_proof, owner_user_id=ctx.user.id,
                           business_id=ctx.business_id).id if proof is not None and proof.filename else None
    total = money(sum(c.amount for c in rows))
    p = CommissionPayment(supplier_id=ctx.business_id, representative_id=reps.pop(), amount=total,
                          commission_ids=[str(c.id) for c in rows], method=method, reference=reference,
                          proof_file_id=proof_id, recorded_by=ctx.user.id)
    db.add(p)
    for c in rows:
        c.status, c.paid_at = CS.paid, utcnow()
    with system_context(db):
        rep = db.get(Representative, p.representative_id)
    notify(db, [rep.user_id], "commission_paid", {"amount": str(total), "supplier": ctx.business.trade_name_ar},
           link="/app/rep/commissions", entity_type="commission_payment", entity_id=p.id)
    audit(db, "commission.payment", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="commission_payment", entity_id=p.id, changes={"amount": total, "ids": p.commission_ids}, request=request)
    db.commit()
    return payment_out(p)


@router.get("/supplier/commission-payments")
def supplier_payments(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.view"))):
    rows = db.scalars(select(CommissionPayment).where(CommissionPayment.supplier_id == ctx.business_id)
                      .order_by(CommissionPayment.paid_at.desc())).all()
    return [payment_out(p) for p in rows]


class AdjustIn(BaseModel):
    amount_delta: Decimal = Field(ge=-1_000_000, le=1_000_000)
    note: str = Field(min_length=5, max_length=2000)


@router.post("/supplier/commissions/{cid}/adjust")
def adjust(cid: uuid.UUID, data: AdjustIn, request: Request, db: Session = Depends(get_db),
           ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    c = db.get(Commission, cid)
    if c is None or c.supplier_id != ctx.business_id:
        raise NotFound()
    if c.status in (CS.cancelled,):
        raise Conflict("commission_closed")
    new_amount = money(c.amount + data.amount_delta)
    if new_amount < 0:
        raise ValidationFailed("commission_negative")
    db.add(CommissionAdjustment(commission_id=c.id, amount_delta=data.amount_delta, reason="manual", note=data.note,
                                created_by=ctx.user.id))
    old = c.amount
    c.amount = new_amount
    if c.status == CS.paid:
        c.status = CS.adjusted
    with system_context(db):
        rep = db.get(Representative, c.representative_id)
    notify(db, [rep.user_id], "commission_updated", {"number": "", "amount": str(c.amount), "status": c.status.value},
           link="/app/rep/commissions", entity_type="commission", entity_id=c.id)
    audit(db, "commission.adjust", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="commission",
          entity_id=c.id, changes={"old": old, "new": new_amount}, reason=data.note, request=request)
    db.commit()
    return commission_out(db, c, ctx.principal.locale)


class ResolveIn(BaseModel):
    accept: bool
    resolution: str = Field(min_length=5, max_length=4000)
    resolved_amount: Decimal | None = Field(default=None, ge=0)


@router.post("/supplier/commission-disputes/{did}/resolve")
def resolve(did: uuid.UUID, data: ResolveIn, request: Request, db: Session = Depends(get_db),
            ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    d = db.get(CommissionDispute, did)
    c = db.get(Commission, d.commission_id) if d else None
    if d is None or c is None or c.supplier_id != ctx.business_id:
        raise NotFound()
    if d.status not in (DisputeStatus.open, DisputeStatus.in_review):
        raise Conflict("dispute_closed")
    d.status = DisputeStatus.resolved if data.accept else DisputeStatus.rejected
    d.resolution, d.resolved_by, d.resolved_at = data.resolution, ctx.user.id, utcnow()
    if data.accept and data.resolved_amount is not None and data.resolved_amount != c.amount:
        db.add(CommissionAdjustment(commission_id=c.id, amount_delta=money(data.resolved_amount - c.amount),
                                    reason="dispute_resolution", reference_id=d.id, note=data.resolution, created_by=ctx.user.id))
        c.amount = money(data.resolved_amount)
        d.resolved_amount = c.amount
    prev = CS(d.previous_status) if d.previous_status else CS.pending
    c.status = CS.adjusted if prev == CS.paid and data.accept else prev
    with system_context(db):
        rep = db.get(Representative, c.representative_id)
    notify(db, [rep.user_id], "commission_updated", {"number": "", "amount": str(c.amount), "status": c.status.value},
           link="/app/rep/commissions", entity_type="commission", entity_id=c.id)
    audit(db, "commission.dispute_resolve", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="commission_dispute", entity_id=d.id, changes=data.model_dump(), request=request)
    db.commit()
    return commission_out(db, c, ctx.principal.locale)
