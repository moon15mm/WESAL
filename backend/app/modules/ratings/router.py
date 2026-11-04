"""Ratings tied to real, completed orders; reports & moderation."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, Principal, RepCtx, current_principal, rep_ctx, retailer_ctx, supplier_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.models.business import Business
from app.models.enums import OrderStatus as S
from app.models.enums import RatingStatus, RatingTarget
from app.models.orders import Order
from app.models.reps import Representative
from app.models.system import Rating, RatingReport
from app.modules.notifications.service import members_with_permission, notify

router = APIRouter(tags=["ratings"])

RATEABLE = {S.completed, S.partially_returned, S.fully_returned}


class RatingIn(BaseModel):
    target: RatingTarget
    overall: int = Field(ge=1, le=5)
    product_quality: int | None = Field(default=None, ge=1, le=5)
    delivery_commitment: int | None = Field(default=None, ge=1, le=5)
    communication: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


def rating_out(r: Rating) -> dict:
    return {"id": str(r.id), "order_id": str(r.order_id), "target_type": r.target_type.value, "target_id": str(r.target_id),
            "overall": r.overall, "product_quality": r.product_quality, "delivery_commitment": r.delivery_commitment,
            "communication": r.communication, "comment": r.comment, "status": r.status.value, "reply": r.reply,
            "created_at": r.created_at}


def refresh_aggregate(db: Session, target_type: RatingTarget, target_id: uuid.UUID) -> None:
    with system_context(db):
        avg, n = db.execute(select(func.avg(Rating.overall), func.count()).where(
            Rating.target_type == target_type, Rating.target_id == target_id, Rating.status == RatingStatus.published)).one()
        obj = db.get(Business if target_type == RatingTarget.supplier else Representative, target_id)
        if obj is not None:
            obj.rating_avg = float(avg or 0)
            obj.rating_count = int(n or 0)


@router.post("/retailer/orders/{oid}/ratings", status_code=201)
def rate(oid: uuid.UUID, data: RatingIn, request: Request, db: Session = Depends(get_db),
         ctx: BusinessCtx = Depends(retailer_ctx("retailer.ratings.create"))):
    o = db.get(Order, oid)
    if o is None or o.retailer_id != ctx.business_id:
        raise NotFound()
    if o.status not in RATEABLE:
        raise Conflict("order_not_rateable")
    if data.target == RatingTarget.representative and not o.representative_id:
        raise ValidationFailed("order_has_no_representative")
    target_id = o.supplier_id if data.target == RatingTarget.supplier else o.representative_id
    if db.scalar(select(Rating.id).where(Rating.order_id == o.id, Rating.rater_business_id == ctx.business_id,
                                         Rating.target_type == data.target)):
        raise Conflict("already_rated")
    r = Rating(order_id=o.id, rater_business_id=ctx.business_id, rater_user_id=ctx.user.id, target_type=data.target,
               target_id=target_id, **data.model_dump(exclude={"target"}))
    db.add(r)
    db.flush()
    refresh_aggregate(db, data.target, target_id)
    if data.target == RatingTarget.supplier:
        notify(db, members_with_permission(db, o.supplier_id), "rating_received", {"stars": data.overall, "number": o.number})
    else:
        with system_context(db):
            rep = db.get(Representative, o.representative_id)
        notify(db, [rep.user_id], "rating_received", {"stars": data.overall, "number": o.number})
    audit(db, "rating.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="rating",
          entity_id=r.id, request=request)
    db.commit()
    return rating_out(r)


@router.get("/ratings")
def list_ratings(target: RatingTarget, target_id: uuid.UUID, db: Session = Depends(get_db),
                 principal: Principal = Depends(current_principal)):
    rows = db.scalars(select(Rating).where(Rating.target_type == target, Rating.target_id == target_id,
                                           Rating.status == RatingStatus.published).order_by(Rating.created_at.desc()).limit(100)).all()
    return [rating_out(r) for r in rows]


class ReportIn(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


class ReplyIn(BaseModel):
    reply: str = Field(min_length=2, max_length=2000)


def _flag(db: Session, r: Rating, user_id, reason: str) -> None:
    db.add(RatingReport(rating_id=r.id, reported_by=user_id, reason=reason))
    r.status = RatingStatus.flagged
    refresh_aggregate(db, r.target_type, r.target_id)


@router.post("/supplier/ratings/{rid}/report")
def supplier_report(rid: uuid.UUID, data: ReportIn, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    r = db.get(Rating, rid)
    if r is None or r.target_type != RatingTarget.supplier or r.target_id != ctx.business_id:
        raise NotFound()
    _flag(db, r, ctx.user.id, data.reason)
    db.commit()
    return rating_out(r)


@router.post("/supplier/ratings/{rid}/reply")
def supplier_reply(rid: uuid.UUID, data: ReplyIn, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    r = db.get(Rating, rid)
    if r is None or r.target_type != RatingTarget.supplier or r.target_id != ctx.business_id:
        raise NotFound()
    r.reply = data.reply
    db.commit()
    return rating_out(r)


@router.get("/supplier/ratings")
def supplier_ratings(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(Rating).where(Rating.target_type == RatingTarget.supplier, Rating.target_id == ctx.business_id)
                      .order_by(Rating.created_at.desc()).limit(200)).all()
    return [rating_out(r) for r in rows]


@router.get("/rep/ratings")
def rep_ratings(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rows = db.scalars(select(Rating).where(Rating.target_type == RatingTarget.representative, Rating.target_id == ctx.rep.id)
                      .order_by(Rating.created_at.desc()).limit(200)).all()
    return [rating_out(r) for r in rows]


@router.post("/rep/ratings/{rid}/report")
def rep_report(rid: uuid.UUID, data: ReportIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    r = db.get(Rating, rid)
    if r is None or r.target_type != RatingTarget.representative or r.target_id != ctx.rep.id:
        raise NotFound()
    _flag(db, r, ctx.user.id, data.reason)
    db.commit()
    return rating_out(r)
