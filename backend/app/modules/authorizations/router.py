"""Authorizations (تفويضات) and commission agreements."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, supplier_ctx
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.i18n import localized
from app.core.utils import next_number, utcnow
from app.models.business import Business, City
from app.models.catalog import Brand, Category, Product, SupplierProduct
from app.models.enums import AuthorizationStatus as S
from app.models.enums import (
    AuthorizationType,
    BusinessStatus,
    BusinessType,
    CommissionBasis,
    CommissionScope,
    RepCompanyRelation,
    RepCompanyStatus,
    VerificationStatus,
)
from app.models.reps import (
    Authorization,
    AuthorizationArea,
    AuthorizationHistory,
    AuthorizationProduct,
    CommissionAgreement,
    CommissionRule,
    Representative,
    RepresentativeCompany,
)
from app.modules.authorizations.service import snapshot, terms_hash, transition
from app.modules.common import business_brief, city_out
from app.modules.notifications.service import members_with_permission, notify

router = APIRouter(tags=["authorizations"])


# ------------------------------------------------------------------ serializers
def auth_out(db: Session, a: Authorization, locale: str, history: bool = False) -> dict:
    cities = {c.id: c for c in db.scalars(select(City).where(City.id.in_([x.city_id for x in a.areas])))} if a.areas else {}
    out = {
        "id": str(a.id), "number": a.number, "status": a.status.value, "type": a.type.value, "initiated_by": a.initiated_by,
        "supplier": business_brief(a.supplier, locale),
        "representative": {"id": str(a.representative.id), "display_name": a.representative.display_name,
                           "kind": a.representative.kind.value,
                           "verification_status": a.representative.verification_status.value,
                           "rating_avg": a.representative.rating_avg},
        "request_message": a.request_message, "all_products": a.all_products, "all_areas": a.all_areas,
        "products": [{"product_id": str(x.product_id) if x.product_id else None, "category_id": x.category_id,
                      "brand_id": str(x.brand_id) if x.brand_id else None} for x in a.products],
        "areas": [{"city": city_out(cities.get(x.city_id), locale), "city_id": x.city_id, "district": x.district} for x in a.areas],
        "start_date": a.start_date, "end_date": a.end_date, "terms": a.terms, "terms_hash": a.terms_hash,
        "accepted_at": a.accepted_at, "status_reason": a.status_reason, "version": a.version,
        "agreement": agreement_out(a.agreement) if a.agreement else None,
        "renewed_from_id": str(a.renewed_from_id) if a.renewed_from_id else None,
        "created_at": a.created_at, "updated_at": a.updated_at,
    }
    if history:
        rows = db.scalars(select(AuthorizationHistory).where(AuthorizationHistory.authorization_id == a.id)
                          .order_by(AuthorizationHistory.created_at)).all()
        out["history"] = [{"action": h.action, "from": h.from_status, "to": h.to_status, "reason": h.reason,
                           "actor_user_id": str(h.actor_user_id) if h.actor_user_id else None, "at": h.created_at} for h in rows]
    return out


def agreement_out(g: CommissionAgreement) -> dict:
    return {"id": str(g.id), "name": g.name, "description": g.description, "eligible_after": g.eligible_after,
            "hold_days": g.hold_days, "is_active": g.is_active,
            "rules": [{"id": str(r.id), "basis": r.basis.value, "rate": r.rate, "scope": r.scope.value,
                       "product_id": str(r.product_id) if r.product_id else None, "category_id": r.category_id,
                       "brand_id": str(r.brand_id) if r.brand_id else None, "min_order_value": r.min_order_value,
                       "priority": r.priority} for r in g.rules]}


def _notify_supplier(db, a: Authorization, event: str, params: dict) -> None:
    notify(db, members_with_permission(db, a.supplier_id, "supplier.reps.manage"), event, params,
           link=f"/app/supplier/authorizations/{a.id}", entity_type="authorization", entity_id=a.id)


def _notify_rep(db, a: Authorization, event: str, params: dict) -> None:
    notify(db, [a.representative.user_id], event, params, link=f"/app/rep/authorizations/{a.id}",
           entity_type="authorization", entity_id=a.id)


# ------------------------------------------------------------------ commission agreements
class RuleIn(BaseModel):
    basis: CommissionBasis
    rate: Decimal = Field(ge=0, le=100000)
    scope: CommissionScope = CommissionScope.all
    product_id: uuid.UUID | None = None
    category_id: int | None = None
    brand_id: uuid.UUID | None = None
    min_order_value: Decimal | None = Field(default=None, ge=0)
    priority: int = Field(default=100, ge=1, le=1000)

    @model_validator(mode="after")
    def _scope(self):
        need = {CommissionScope.product: self.product_id, CommissionScope.category: self.category_id,
                CommissionScope.brand: self.brand_id}
        if self.scope != CommissionScope.all and not need[self.scope]:
            raise ValueError("scope target required")
        if self.basis == CommissionBasis.percent and self.rate > 100:
            raise ValueError("percent cannot exceed 100")
        return self


class AgreementIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    eligible_after: Literal["delivered", "completed"] = "completed"
    hold_days: int = Field(default=7, ge=0, le=90)
    is_active: bool = True
    rules: list[RuleIn] = Field(min_length=1, max_length=100)


@router.get("/supplier/commission-agreements")
def list_agreements(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(CommissionAgreement).where(CommissionAgreement.supplier_id == ctx.business_id)
                      .order_by(CommissionAgreement.created_at.desc())).all()
    return [agreement_out(g) for g in rows]


def _save_agreement(db: Session, g: CommissionAgreement, data: AgreementIn) -> None:
    for r in data.rules:
        if r.product_id and db.get(Product, r.product_id) is None:
            raise ValidationFailed("invalid_product")
        if r.category_id and db.get(Category, r.category_id) is None:
            raise ValidationFailed("invalid_category")
        if r.brand_id and db.get(Brand, r.brand_id) is None:
            raise ValidationFailed("invalid_brand")
    g.name, g.description, g.eligible_after, g.hold_days, g.is_active = (
        data.name, data.description, data.eligible_after, data.hold_days, data.is_active)
    g.rules.clear()
    db.flush()
    for r in data.rules:
        g.rules.append(CommissionRule(**r.model_dump()))


@router.post("/supplier/commission-agreements", status_code=201)
def create_agreement(data: AgreementIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    g = CommissionAgreement(supplier_id=ctx.business_id, name=data.name)
    db.add(g)
    db.flush()
    _save_agreement(db, g, data)
    audit(db, "commission_agreement.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="commission_agreement", entity_id=g.id, changes=data.model_dump(), request=request)
    db.commit()
    return agreement_out(g)


@router.put("/supplier/commission-agreements/{agreement_id}")
def update_agreement(agreement_id: uuid.UUID, data: AgreementIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(supplier_ctx("supplier.commissions.manage"))):
    g = db.get(CommissionAgreement, agreement_id)
    if g is None or g.supplier_id != ctx.business_id:
        raise NotFound()
    _save_agreement(db, g, data)
    # changing commission terms requires representatives to accept the new terms
    for a in db.scalars(select(Authorization).where(Authorization.agreement_id == g.id, Authorization.status == S.active)):
        a.version += 1
        a.terms_hash = terms_hash(a)
        transition(db, a, S.pending_rep, ctx.user.id, "terms_changed", "commission agreement updated")
        _notify_rep(db, a, "authorization_issued", {"supplier": ctx.business.display_name("ar"), "number": a.number})
    audit(db, "commission_agreement.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="commission_agreement", entity_id=g.id, changes=data.model_dump(), request=request)
    db.commit()
    return agreement_out(g)


# ------------------------------------------------------------------ supplier side
class ScopeIn(BaseModel):
    product_id: uuid.UUID | None = None
    category_id: int | None = None
    brand_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one(self):
        if sum(x is not None for x in (self.product_id, self.category_id, self.brand_id)) != 1:
            raise ValueError("exactly one of product_id/category_id/brand_id")
        return self


class AreaIn(BaseModel):
    city_id: int
    district: str | None = Field(default=None, max_length=120)


class AuthorizationTermsIn(BaseModel):
    type: AuthorizationType = AuthorizationType.full_sales
    agreement_id: uuid.UUID | None = None
    all_products: bool = False
    all_areas: bool = False
    products: list[ScopeIn] = []
    areas: list[AreaIn] = []
    start_date: date
    end_date: date | None = None
    terms: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _check(self):
        if not self.all_products and not self.products:
            raise ValueError("product scope required")
        if not self.all_areas and not self.areas:
            raise ValueError("area scope required")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date before start_date")
        return self


class AuthorizationCreateIn(AuthorizationTermsIn):
    representative_id: uuid.UUID
    issue: bool = True  # False keeps it as draft


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


def _get_supplier_auth(db: Session, ctx: BusinessCtx, auth_id: uuid.UUID) -> Authorization:
    a = db.get(Authorization, auth_id)
    if a is None or a.supplier_id != ctx.business_id:
        raise NotFound()
    return a


def _apply_terms(db: Session, ctx: BusinessCtx, a: Authorization, data: AuthorizationTermsIn) -> None:
    if data.agreement_id:
        g = db.get(CommissionAgreement, data.agreement_id)
        if g is None or g.supplier_id != ctx.business_id or not g.is_active:
            raise ValidationFailed("invalid_agreement")
    elif data.type != AuthorizationType.promotion_only:
        raise ValidationFailed("agreement_required", fields={"agreement_id": "required"})
    for s in data.products:
        if s.product_id:
            offered = db.scalar(select(SupplierProduct.id).where(SupplierProduct.supplier_id == ctx.business_id,
                                                                 SupplierProduct.product_id == s.product_id))
            if not offered:
                raise ValidationFailed("invalid_product")
        if s.category_id and db.get(Category, s.category_id) is None:
            raise ValidationFailed("invalid_category")
        if s.brand_id and db.get(Brand, s.brand_id) is None:
            raise ValidationFailed("invalid_brand")
    for ar in data.areas:
        if db.get(City, ar.city_id) is None:
            raise ValidationFailed("invalid_city")
    a.type, a.agreement_id = data.type, data.agreement_id
    a.all_products, a.all_areas = data.all_products, data.all_areas
    a.start_date, a.end_date, a.terms = data.start_date, data.end_date, data.terms
    a.products.clear()
    a.areas.clear()
    db.flush()
    for s in ([] if data.all_products else data.products):
        a.products.append(AuthorizationProduct(**s.model_dump()))
    for ar in ([] if data.all_areas else data.areas):
        a.areas.append(AuthorizationArea(**ar.model_dump()))
    db.flush()
    db.refresh(a)
    a.terms_hash = terms_hash(a)


@router.get("/supplier/authorizations")
def supplier_list(status: S | None = None, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    stmt = select(Authorization).where(Authorization.supplier_id == ctx.business_id).order_by(Authorization.created_at.desc())
    if status:
        stmt = stmt.where(Authorization.status == status)
    return [auth_out(db, a, ctx.principal.locale) for a in db.scalars(stmt.limit(500))]


@router.get("/supplier/authorizations/{auth_id}")
def supplier_get(auth_id: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    return auth_out(db, _get_supplier_auth(db, ctx, auth_id), ctx.principal.locale, history=True)


@router.post("/supplier/authorizations", status_code=201)
def supplier_create(data: AuthorizationCreateIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    with system_context(db):
        rep = db.get(Representative, data.representative_id)
    if rep is None or not rep.is_active:
        raise ValidationFailed("invalid_representative")
    open_exists = db.scalar(select(Authorization.id).where(
        Authorization.supplier_id == ctx.business_id, Authorization.representative_id == rep.id,
        Authorization.status.in_([S.draft, S.sent, S.pending_rep, S.active, S.suspended])))
    if open_exists:
        raise Conflict("authorization_exists")
    a = Authorization(number=next_number(db, "AUT"), supplier_id=ctx.business_id, representative_id=rep.id,
                      status=S.draft, initiated_by="supplier")
    db.add(a)
    db.flush()
    _apply_terms(db, ctx, a, data)
    db.add(AuthorizationHistory(authorization_id=a.id, action="created", to_status=S.draft.value, actor_user_id=ctx.user.id,
                                snapshot=snapshot(a)))
    if data.issue:
        transition(db, a, S.pending_rep, ctx.user.id, "issued")
        _notify_rep(db, a, "authorization_issued", {"supplier": ctx.business.trade_name_ar, "number": a.number})
    audit(db, "authorization.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="authorization", entity_id=a.id, changes=snapshot(a), request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


@router.put("/supplier/authorizations/{auth_id}")
def supplier_update_terms(auth_id: uuid.UUID, data: AuthorizationTermsIn, request: Request, db: Session = Depends(get_db),
                          ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    a = _get_supplier_auth(db, ctx, auth_id)
    if a.status in (S.expired, S.cancelled):
        raise Conflict("authorization_closed")
    before = snapshot(a)
    _apply_terms(db, ctx, a, data)
    a.version += 1
    if a.status in (S.sent,):
        pass
    elif a.status in (S.active, S.suspended, S.pending_rep):
        # changed terms always need the representative's acceptance again
        if a.status == S.suspended:
            raise Conflict("authorization_suspended")
        transition(db, a, S.pending_rep, ctx.user.id, "terms_changed")
        _notify_rep(db, a, "authorization_issued", {"supplier": ctx.business.trade_name_ar, "number": a.number})
    audit(db, "authorization.update_terms", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="authorization", entity_id=a.id, changes={"before": before, "after": snapshot(a)}, request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


@router.post("/supplier/authorizations/{auth_id}/issue")
def supplier_issue(auth_id: uuid.UUID, data: AuthorizationTermsIn, request: Request, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    """Approve a representative's request (or a draft) by issuing terms for acceptance."""
    a = _get_supplier_auth(db, ctx, auth_id)
    if a.status not in (S.sent, S.draft):
        raise Conflict("authorization_invalid_transition")
    _apply_terms(db, ctx, a, data)
    transition(db, a, S.pending_rep, ctx.user.id, "issued")
    _notify_rep(db, a, "authorization_issued", {"supplier": ctx.business.trade_name_ar, "number": a.number})
    audit(db, "authorization.issue", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="authorization", entity_id=a.id, changes=snapshot(a), request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


def _supplier_status_action(action: str, to: S, allowed_from: set[S], event: str):
    def handler(auth_id: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
        a = _get_supplier_auth(db, ctx, auth_id)
        if a.status not in allowed_from:
            raise Conflict("authorization_invalid_transition", params={"from": a.status.value, "to": to.value})
        transition(db, a, to, ctx.user.id, action, data.reason)
        _notify_rep(db, a, event, {"supplier": ctx.business.trade_name_ar, "number": a.number, "status": to.value})
        audit(db, f"authorization.{action}", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
              entity_type="authorization", entity_id=a.id, reason=data.reason, request=request)
        db.commit()
        return auth_out(db, a, ctx.principal.locale)

    return handler


router.post("/supplier/authorizations/{auth_id}/decline")(
    _supplier_status_action("declined", S.cancelled, {S.sent}, "authorization_declined"))
router.post("/supplier/authorizations/{auth_id}/suspend")(
    _supplier_status_action("suspended", S.suspended, {S.active}, "authorization_status_changed"))
router.post("/supplier/authorizations/{auth_id}/resume")(
    _supplier_status_action("resumed", S.active, {S.suspended}, "authorization_status_changed"))
router.post("/supplier/authorizations/{auth_id}/cancel")(
    _supplier_status_action("cancelled", S.cancelled, {S.draft, S.sent, S.pending_rep, S.active, S.suspended},
                            "authorization_status_changed"))


class RenewIn(BaseModel):
    start_date: date
    end_date: date | None = None


@router.post("/supplier/authorizations/{auth_id}/renew", status_code=201)
def supplier_renew(auth_id: uuid.UUID, data: RenewIn, request: Request, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    old = _get_supplier_auth(db, ctx, auth_id)
    if old.status not in (S.active, S.expired):
        raise Conflict("authorization_invalid_transition")
    if data.end_date and data.end_date < data.start_date:
        raise ValidationFailed("invalid_dates")
    new = Authorization(number=next_number(db, "AUT"), supplier_id=old.supplier_id, representative_id=old.representative_id,
                        type=old.type, status=S.pending_rep, initiated_by="supplier", agreement_id=old.agreement_id,
                        all_products=old.all_products, all_areas=old.all_areas, start_date=data.start_date,
                        end_date=data.end_date, terms=old.terms, renewed_from_id=old.id)
    db.add(new)
    db.flush()
    for p in old.products:
        new.products.append(AuthorizationProduct(product_id=p.product_id, category_id=p.category_id, brand_id=p.brand_id))
    for ar in old.areas:
        new.areas.append(AuthorizationArea(city_id=ar.city_id, district=ar.district))
    db.flush()
    db.refresh(new)
    new.terms_hash = terms_hash(new)
    db.add(AuthorizationHistory(authorization_id=new.id, action="renewal_issued", to_status=S.pending_rep.value,
                                actor_user_id=ctx.user.id, snapshot=snapshot(new), reason=f"renewal of {old.number}"))
    db.add(AuthorizationHistory(authorization_id=old.id, action="renewed", from_status=old.status.value,
                                to_status=old.status.value, actor_user_id=ctx.user.id, reason=f"renewed as {new.number}"))
    _notify_rep(db, new, "authorization_issued", {"supplier": ctx.business.trade_name_ar, "number": new.number})
    audit(db, "authorization.renew", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="authorization", entity_id=new.id, changes={"renewed_from": old.id}, request=request)
    db.commit()
    return auth_out(db, new, ctx.principal.locale)


# ------------------------------------------------------------------ representative side
class RepRequestIn(BaseModel):
    supplier_id: uuid.UUID
    message: str | None = Field(default=None, max_length=2000)
    category_ids: list[int] = []
    city_ids: list[int] = []


def _get_rep_auth(db: Session, ctx: RepCtx, auth_id: uuid.UUID) -> Authorization:
    a = db.get(Authorization, auth_id)
    if a is None or a.representative_id != ctx.rep.id:
        raise NotFound()
    return a


@router.get("/rep/authorizations")
def rep_list(status: S | None = None, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    stmt = select(Authorization).where(Authorization.representative_id == ctx.rep.id).order_by(Authorization.created_at.desc())
    if status:
        stmt = stmt.where(Authorization.status == status)
    return [auth_out(db, a, ctx.principal.locale) for a in db.scalars(stmt)]


@router.get("/rep/authorizations/{auth_id}")
def rep_get(auth_id: uuid.UUID, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return auth_out(db, _get_rep_auth(db, ctx, auth_id), ctx.principal.locale, history=True)


@router.post("/rep/authorizations", status_code=201)
def rep_request(data: RepRequestIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    with system_context(db):
        sup = db.get(Business, data.supplier_id)
    if sup is None or sup.type != BusinessType.supplier or sup.status != BusinessStatus.active or \
            sup.verification_status != VerificationStatus.verified:
        raise ValidationFailed("invalid_supplier")
    exists = db.scalar(select(Authorization.id).where(
        Authorization.supplier_id == sup.id, Authorization.representative_id == ctx.rep.id,
        Authorization.status.in_([S.draft, S.sent, S.pending_rep, S.active, S.suspended])))
    if exists:
        raise Conflict("authorization_exists")
    a = Authorization(number=next_number(db, "AUT"), supplier_id=sup.id, representative_id=ctx.rep.id, status=S.sent,
                      initiated_by="representative", request_message=data.message, all_products=not data.category_ids,
                      all_areas=not data.city_ids, start_date=utcnow().date())
    db.add(a)
    db.flush()
    for cid in data.category_ids:
        if db.get(Category, cid):
            a.products.append(AuthorizationProduct(category_id=cid))
    for cid in data.city_ids:
        if db.get(City, cid):
            a.areas.append(AuthorizationArea(city_id=cid))
    db.add(AuthorizationHistory(authorization_id=a.id, action="requested", to_status=S.sent.value, actor_user_id=ctx.user.id))
    with system_context(db):
        _notify_supplier(db, a, "authorization_requested", {"representative": ctx.rep.display_name, "number": a.number})
    audit(db, "authorization.request", actor_user_id=ctx.user.id, entity_type="authorization", entity_id=a.id, request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


class AcceptIn(BaseModel):
    terms_hash: str = Field(min_length=64, max_length=64)  # the exact terms version the rep reviewed


@router.post("/rep/authorizations/{auth_id}/accept")
def rep_accept(auth_id: uuid.UUID, data: AcceptIn, request: Request, db: Session = Depends(get_db),
               ctx: RepCtx = Depends(rep_ctx())):
    a = _get_rep_auth(db, ctx, auth_id)
    if a.status != S.pending_rep:
        raise Conflict("authorization_invalid_transition")
    if ctx.rep.verification_status != VerificationStatus.verified:
        raise Forbidden("representative_not_verified")
    if data.terms_hash != a.terms_hash:
        raise Conflict("authorization_terms_changed")
    a.accepted_at = utcnow()
    a.accepted_by = ctx.user.id
    transition(db, a, S.active, ctx.user.id, "accepted")
    rel = db.scalar(select(RepresentativeCompany).where(RepresentativeCompany.representative_id == ctx.rep.id,
                                                        RepresentativeCompany.supplier_id == a.supplier_id))
    if rel is None:
        db.add(RepresentativeCompany(representative_id=ctx.rep.id, supplier_id=a.supplier_id,
                                     relation=RepCompanyRelation.partner, status=RepCompanyStatus.active))
    elif rel.status != RepCompanyStatus.active:
        rel.status, rel.ended_at = RepCompanyStatus.active, None
    with system_context(db):
        _notify_supplier(db, a, "authorization_activated", {"representative": ctx.rep.display_name, "number": a.number})
    audit(db, "authorization.accept", actor_user_id=ctx.user.id, entity_type="authorization", entity_id=a.id,
          changes={"terms_hash": a.terms_hash}, request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


@router.post("/rep/authorizations/{auth_id}/decline")
def rep_decline(auth_id: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                ctx: RepCtx = Depends(rep_ctx())):
    a = _get_rep_auth(db, ctx, auth_id)
    if a.status not in (S.pending_rep, S.sent):
        raise Conflict("authorization_invalid_transition")
    action = "withdrawn" if a.status == S.sent else "declined_by_rep"
    transition(db, a, S.cancelled, ctx.user.id, action, data.reason)
    with system_context(db):
        _notify_supplier(db, a, "authorization_status_changed", {"number": a.number, "status": "cancelled",
                                                                 "supplier": a.supplier.trade_name_ar})
    audit(db, f"authorization.{action}", actor_user_id=ctx.user.id, entity_type="authorization", entity_id=a.id,
          reason=data.reason, request=request)
    db.commit()
    return auth_out(db, a, ctx.principal.locale)


@router.get("/ref/authorization-types")
def authorization_types():
    return [t.value for t in AuthorizationType]


__all__ = ["router", "localized"]
