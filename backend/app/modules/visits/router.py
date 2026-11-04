"""Field visits. Location is captured only at start/end of a visit, only with explicit consent."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, supplier_ctx
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.schemas import PageParams, paginate
from app.core.utils import utcnow
from app.models.business import Branch, Business
from app.models.crm import Customer, Visit
from app.models.enums import (
    AcquisitionSource,
    AuthorizationStatus,
    BusinessType,
    CustomerStatus,
    VisitOutcome,
    VisitPurpose,
    VisitStatus,
)
from app.models.reps import Authorization
from app.modules.crm.service import Owner, ensure_customer

router = APIRouter(tags=["visits"])


def visit_out(v: Visit) -> dict:
    return {"id": str(v.id), "representative_id": str(v.representative_id),
            "supplier_id": str(v.supplier_id) if v.supplier_id else None,
            "customer_id": str(v.customer_id) if v.customer_id else None,
            "customer_name": v.customer.name if v.customer else None,
            "retailer_id": str(v.retailer_id) if v.retailer_id else None, "branch_id": str(v.branch_id) if v.branch_id else None,
            "purpose": v.purpose.value, "status": v.status.value, "scheduled_at": v.scheduled_at, "started_at": v.started_at,
            "ended_at": v.ended_at, "outcome": v.outcome.value if v.outcome else None, "notes": v.notes,
            "discussed_products": v.discussed_products, "order_id": str(v.order_id) if v.order_id else None,
            "next_visit_at": v.next_visit_at, "location_consent": v.location_consent,
            "has_location": v.start_lat is not None, "created_at": v.created_at}


class VisitIn(BaseModel):
    customer_id: uuid.UUID | None = None
    retailer_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    purpose: VisitPurpose
    scheduled_at: datetime | None = None
    start_now: bool = False
    notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _target(self):
        if not (self.customer_id or self.retailer_id):
            raise ValueError("customer_id or retailer_id required")
        if not self.start_now and not self.scheduled_at:
            raise ValueError("scheduled_at required unless start_now")
        return self


class LocationIn(BaseModel):
    consent: bool = False
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class EndIn(LocationIn):
    outcome: VisitOutcome
    notes: str | None = Field(default=None, max_length=4000)
    discussed_products: list[dict] = Field(default=[], max_length=50)
    next_visit_at: datetime | None = None
    order_id: uuid.UUID | None = None


def _get(db: Session, ctx: RepCtx, vid: uuid.UUID) -> Visit:
    v = db.get(Visit, vid)
    if v is None or v.representative_id != ctx.rep.id:
        raise NotFound()
    return v


def _set_location(v: Visit, loc: LocationIn, start: bool) -> None:
    if not loc.consent or loc.lat is None or loc.lng is None:
        return
    v.location_consent = True
    if start:
        v.start_lat, v.start_lng = round(loc.lat, 5), round(loc.lng, 5)
    else:
        v.end_lat, v.end_lng = round(loc.lat, 5), round(loc.lng, 5)


@router.get("/rep/visits")
def list_visits(status: VisitStatus | None = None, date_from: datetime | None = None, date_to: datetime | None = None,
                params: PageParams = Depends(), db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    stmt = select(Visit).where(Visit.representative_id == ctx.rep.id).order_by(Visit.scheduled_at.desc().nulls_last(),
                                                                               Visit.created_at.desc())
    if status:
        stmt = stmt.where(Visit.status == status)
    if date_from:
        stmt = stmt.where(Visit.scheduled_at >= date_from)
    if date_to:
        stmt = stmt.where(Visit.scheduled_at <= date_to)
    return paginate(db, stmt, params, visit_out)


@router.post("/rep/visits", status_code=201)
def create_visit(data: VisitIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    owner = Owner(rep_id=ctx.rep.id)
    customer = None
    if data.customer_id:
        customer = db.get(Customer, data.customer_id)
        if customer is None or customer.owner_representative_id != ctx.rep.id:
            raise ValidationFailed("invalid_customer")
    retailer_id = data.retailer_id or (customer.retailer_id if customer else None)
    branch = None
    if retailer_id:
        retailer = db.get(Business, retailer_id)
        if retailer is None or retailer.type != BusinessType.retailer:
            raise ValidationFailed("invalid_retailer")
        if data.branch_id:
            branch = db.get(Branch, data.branch_id)
            if branch is None or branch.business_id != retailer.id:
                raise ValidationFailed("invalid_branch")
        if customer is None:
            customer = ensure_customer(db, owner, retailer, source=AcquisitionSource.rep_visit, created_by=ctx.user.id, branch=branch)
    if data.supplier_id:
        ok = db.scalar(select(Authorization.id).where(Authorization.representative_id == ctx.rep.id,
                                                      Authorization.supplier_id == data.supplier_id,
                                                      Authorization.status == AuthorizationStatus.active))
        if not ok:
            raise Forbidden("authorization_missing")
    v = Visit(representative_id=ctx.rep.id, supplier_id=data.supplier_id, customer_id=customer.id if customer else None,
              retailer_id=retailer_id, branch_id=branch.id if branch else (customer.branch_id if customer else None),
              purpose=data.purpose, scheduled_at=data.scheduled_at or utcnow(), notes=data.notes,
              status=VisitStatus.in_progress if data.start_now else VisitStatus.scheduled,
              started_at=utcnow() if data.start_now else None)
    db.add(v)
    db.flush()
    db.refresh(v)
    db.commit()
    return visit_out(v)


@router.post("/rep/visits/{vid}/start")
def start_visit(vid: uuid.UUID, data: LocationIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    v = _get(db, ctx, vid)
    if v.status != VisitStatus.scheduled:
        raise Conflict("visit_invalid_transition")
    in_progress = db.scalar(select(Visit.id).where(Visit.representative_id == ctx.rep.id, Visit.status == VisitStatus.in_progress))
    if in_progress:
        raise Conflict("visit_already_in_progress")
    v.status, v.started_at = VisitStatus.in_progress, utcnow()
    _set_location(v, data, start=True)
    db.commit()
    return visit_out(v)


@router.post("/rep/visits/{vid}/end")
def end_visit(vid: uuid.UUID, data: EndIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    v = _get(db, ctx, vid)
    if v.status != VisitStatus.in_progress:
        raise Conflict("visit_invalid_transition")
    if data.order_id:
        from app.models.orders import Order

        o = db.get(Order, data.order_id)
        if o is None or o.representative_id != ctx.rep.id:
            raise ValidationFailed("invalid_order")
        v.order_id = o.id
    v.status, v.ended_at, v.outcome = VisitStatus.completed, utcnow(), data.outcome
    v.notes = data.notes or v.notes
    v.discussed_products = [{"product_id": str(p.get("product_id")), "feedback": str(p.get("feedback", ""))[:500]}
                            for p in data.discussed_products if p.get("product_id")]
    v.next_visit_at = data.next_visit_at
    _set_location(v, data, start=False)
    if v.customer_id:
        c = db.get(Customer, v.customer_id)
        c.last_visit_at = v.ended_at
        if data.next_visit_at:
            c.next_follow_up_at = data.next_visit_at
        if data.outcome == VisitOutcome.not_interested and c.status in (CustomerStatus.lead, CustomerStatus.prospect):
            c.status = CustomerStatus.lost
    if data.next_visit_at:
        db.add(Visit(representative_id=ctx.rep.id, supplier_id=v.supplier_id, customer_id=v.customer_id, retailer_id=v.retailer_id,
                     branch_id=v.branch_id, purpose=VisitPurpose.follow_up, scheduled_at=data.next_visit_at))
    audit(db, "visit.complete", actor_user_id=ctx.user.id, entity_type="visit", entity_id=v.id,
          changes={"outcome": data.outcome.value}, request=request)
    db.commit()
    return visit_out(v)


@router.post("/rep/visits/{vid}/cancel")
def cancel_visit(vid: uuid.UUID, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    v = _get(db, ctx, vid)
    if v.status not in (VisitStatus.scheduled, VisitStatus.in_progress):
        raise Conflict("visit_invalid_transition")
    v.status = VisitStatus.cancelled
    db.commit()
    return visit_out(v)


@router.get("/supplier/visits")
def supplier_visits(representative_id: uuid.UUID | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    stmt = select(Visit).where(Visit.supplier_id == ctx.business_id).order_by(Visit.created_at.desc())
    if representative_id:
        stmt = stmt.where(Visit.representative_id == representative_id)
    return paginate(db, stmt, params, visit_out)
