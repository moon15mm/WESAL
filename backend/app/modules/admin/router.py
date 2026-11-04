"""Platform administration (requires platform role + TOTP-verified session)."""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import AdminCtx, admin_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.i18n import SUPPORTED_LOCALES, catalog, localized, missing_keys, set_overrides
from app.core.schemas import PageParams, paginate
from app.core.utils import money, slugify, utcnow
from app.models.business import Business, BusinessDocument, BusinessMember, City, Region
from app.models.catalog import Brand, Category, Product, SupplierProduct
from app.models.commissions import Commission, CommissionDispute
from app.models.enums import (
    AdStatus,
    BusinessStatus,
    BusinessType,
    CommissionStatus,
    ComplaintKind,
    ComplaintStatus as CS,
    DataRequestStatus,
    DocumentStatus,
    OrderStatus as S,
    OutboxStatus,
    ProductStatus,
    RatingStatus,
    SubscriptionStatus,
    UserStatus,
    VerificationStatus,
)
from app.models.identity import Role, User, UserRole, UserSession
from app.models.orders import Order
from app.models.reps import Representative, RepresentativeDocument
from app.models.system import (
    Advertisement,
    AuditLog,
    Complaint,
    ComplaintMessage,
    ContactMessage,
    ContentPage,
    DataRequest,
    JobRun,
    Language,
    NotificationDelivery,
    PlatformSetting,
    Rating,
    Subscription,
    SubscriptionPlan,
    TranslationOverride,
)
from app.modules.common import business_brief, city_out, file_url
from app.modules.notifications.service import members_with_permission, notify
from app.modules.orders import service as order_svc
from app.modules.orders.router import order_out
from app.modules.ratings.router import refresh_aggregate

router = APIRouter(prefix="/admin", tags=["admin"])


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def dashboard(days: int = 30, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.dashboard"))):
    days = max(1, min(days, 365))
    start = utcnow() - timedelta(days=days)
    loc = ctx.principal.locale
    sales = S.approved, S.preparing, S.ready, S.out_for_delivery, S.delivered, S.completed, S.partially_returned, S.disputed
    users = db.scalar(select(func.count()).select_from(User).where(User.status != UserStatus.deleted)) or 0
    new_users = db.scalar(select(func.count()).select_from(User).where(User.created_at >= start)) or 0
    count_b = lambda t, extra=True: db.scalar(select(func.count()).select_from(Business).where(Business.type == t, extra)) or 0  # noqa: E731
    active_sup = db.scalar(select(func.count(func.distinct(Order.supplier_id))).where(Order.created_at >= start)) or 0
    active_store = db.scalar(select(func.count(func.distinct(Order.retailer_id))).where(Order.created_at >= start)) or 0
    active_rep = db.scalar(select(func.count(func.distinct(Order.representative_id))).where(Order.created_at >= start,
                                                                                            Order.representative_id.isnot(None))) or 0
    gmv, n_sales = db.execute(select(func.coalesce(func.sum(Order.total), 0), func.count()).where(
        Order.status.in_(sales), Order.created_at >= start)).one()
    n_orders = db.scalar(select(func.count()).select_from(Order).where(Order.created_at >= start)) or 0
    submitted = db.scalar(select(func.count()).select_from(Order).where(Order.created_at >= start, Order.submitted_at.isnot(None))) or 0
    completed = db.scalar(select(func.count()).select_from(Order).where(Order.created_at >= start, Order.status == S.completed)) or 0
    disputes = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.kind == ComplaintKind.order_dispute,
                                                                           Complaint.status.notin_([CS.resolved, CS.closed, CS.rejected]))) or 0
    open_complaints = db.scalar(select(func.count()).select_from(Complaint).where(Complaint.status.in_([CS.open, CS.in_review, CS.awaiting_response]))) or 0
    pending_verifications = (db.scalar(select(func.count()).select_from(Business).where(Business.verification_status == VerificationStatus.pending)) or 0) + \
        (db.scalar(select(func.count()).select_from(Representative).where(Representative.verification_status == VerificationStatus.pending)) or 0)
    revenue = db.scalar(select(func.coalesce(func.sum(SubscriptionPlan.price_monthly), 0)).select_from(Subscription).join(
        SubscriptionPlan, SubscriptionPlan.id == Subscription.plan_id).where(Subscription.status == SubscriptionStatus.active)) or 0
    b = func.date_trunc("day", Order.created_at)
    series = [{"period": p.date().isoformat(), "orders": c, "value": money(v)} for p, c, v in db.execute(
        select(b, func.count(), func.coalesce(func.sum(Order.total), 0)).where(Order.created_at >= start, Order.status.in_(sales))
        .group_by(b).order_by(b)).all()]
    regions = db.execute(select(Region, func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).join(
        City, City.region_id == Region.id).join(Order, Order.city_id == City.id).where(Order.created_at >= start, Order.status.in_(sales))
        .group_by(Region.id).order_by(func.sum(Order.total).desc())).all()
    statuses = {s.value: c for s, c in db.execute(select(Order.status, func.count()).where(Order.created_at >= start).group_by(Order.status))}
    return {
        "days": days,
        "kpis": {"users": users, "new_users": new_users, "suppliers": count_b(BusinessType.supplier),
                 "verified_suppliers": count_b(BusinessType.supplier, Business.verification_status == VerificationStatus.verified),
                 "stores": count_b(BusinessType.retailer),
                 "representatives": db.scalar(select(func.count()).select_from(Representative)) or 0,
                 "active_suppliers": active_sup, "active_stores": active_store, "active_representatives": active_rep,
                 "gmv": money(gmv), "orders": n_orders, "sales_orders": n_sales, "completed": completed,
                 "conversion_rate": round(n_sales / submitted * 100, 1) if submitted else 0,
                 "avg_order_value": money(gmv / n_sales) if n_sales else Decimal("0"),
                 "open_disputes": disputes, "open_complaints": open_complaints, "pending_verifications": pending_verifications,
                 "platform_mrr": money(revenue)},
        "series": series, "statuses": statuses,
        "regions": [{"region": localized(r.name, loc), "orders": c, "value": money(v)} for r, c, v in regions],
    }


# ------------------------------------------------------------------ users
def user_out(u: User) -> dict:
    return {"id": str(u.id), "full_name": u.full_name, "email": u.email, "phone": u.phone, "status": u.status.value,
            "locale": u.locale, "email_verified": u.email_verified_at is not None, "phone_verified": u.phone_verified_at is not None,
            "mfa_enabled": u.mfa_enabled, "last_login_at": u.last_login_at, "created_at": u.created_at,
            "roles": [r.role.code for r in u.roles], "suspended_reason": u.suspended_reason}


@router.get("/users")
def users(q: str | None = None, status: UserStatus | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
          ctx: AdminCtx = Depends(admin_ctx("admin.users.view"))):
    stmt = select(User).order_by(User.created_at.desc())
    if q:
        stmt = stmt.where(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"), User.phone.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(User.status == status)
    return paginate(db, stmt, params, user_out)


@router.get("/users/{uid}")
def user_detail(uid: uuid.UUID, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.users.view"))):
    u = db.get(User, uid)
    if u is None:
        raise NotFound()
    members = db.scalars(select(BusinessMember).where(BusinessMember.user_id == u.id)).all()
    rep = db.scalar(select(Representative).where(Representative.user_id == u.id))
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == u.id, UserSession.revoked_at.is_(None),
                                                    UserSession.expires_at > utcnow())).all()
    return {**user_out(u), "memberships": [{"business": business_brief(m.business, ctx.principal.locale), "role": m.role.code,
                                            "status": m.status.value} for m in members],
            "representative_id": str(rep.id) if rep else None, "active_sessions": len(sessions)}


@router.post("/users/{uid}/suspend")
def suspend_user(uid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                 ctx: AdminCtx = Depends(admin_ctx("admin.users.manage"))):
    u = db.get(User, uid)
    if u is None:
        raise NotFound()
    if u.id == ctx.user.id:
        raise Conflict("cannot_suspend_self")
    u.status, u.suspended_reason = UserStatus.suspended, data.reason
    for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id, UserSession.revoked_at.is_(None))):
        s.revoked_at = utcnow()
    audit(db, "admin.user_suspend", actor_user_id=ctx.user.id, entity_type="user", entity_id=u.id, reason=data.reason, request=request)
    db.commit()
    return user_out(u)


@router.post("/users/{uid}/activate")
def activate_user(uid: uuid.UUID, request: Request, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.users.manage"))):
    u = db.get(User, uid)
    if u is None:
        raise NotFound()
    u.status, u.suspended_reason, u.locked_until, u.failed_login_count = UserStatus.active, None, None, 0
    audit(db, "admin.user_activate", actor_user_id=ctx.user.id, entity_type="user", entity_id=u.id, request=request)
    db.commit()
    return user_out(u)


class RoleGrantIn(BaseModel):
    role_code: Literal["platform_admin", "platform_support", "platform_reviewer"]
    grant: bool = True


@router.post("/users/{uid}/platform-role")
def platform_role(uid: uuid.UUID, data: RoleGrantIn, request: Request, db: Session = Depends(get_db),
                  ctx: AdminCtx = Depends(admin_ctx("admin.roles.manage"))):
    u = db.get(User, uid)
    role = db.scalar(select(Role).where(Role.code == data.role_code, Role.business_id.is_(None)))
    if u is None or role is None:
        raise NotFound()
    existing = db.get(UserRole, (u.id, role.id))
    if data.grant and existing is None:
        db.add(UserRole(user_id=u.id, role_id=role.id, granted_by=ctx.user.id))
    elif not data.grant and existing is not None:
        if u.id == ctx.user.id and data.role_code == "platform_admin":
            raise Conflict("cannot_revoke_own_admin")
        db.delete(existing)
    audit(db, "admin.platform_role", actor_user_id=ctx.user.id, entity_type="user", entity_id=u.id, changes=data.model_dump(),
          request=request)
    db.commit()
    db.refresh(u)
    return user_out(u)


# ------------------------------------------------------------------ businesses & verification
@router.get("/businesses")
def businesses(type: BusinessType | None = None, verification: VerificationStatus | None = None, q: str | None = None,
               params: PageParams = Depends(), db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.businesses.verify"))):
    stmt = select(Business).order_by(Business.created_at.desc())
    if type:
        stmt = stmt.where(Business.type == type)
    if verification:
        stmt = stmt.where(Business.verification_status == verification)
    if q:
        stmt = stmt.where(or_(Business.trade_name_ar.ilike(f"%{q}%"), Business.trade_name_en.ilike(f"%{q}%"),
                              Business.cr_number.ilike(f"%{q}%")))
    return paginate(db, stmt, params, lambda b: {**business_brief(b, ctx.principal.locale), "status": b.status.value,
                                                 "cr_number": b.cr_number, "created_at": b.created_at})


@router.get("/businesses/{bid}")
def business_detail(bid: uuid.UUID, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.businesses.verify"))):
    b = db.get(Business, bid)
    if b is None:
        raise NotFound()
    docs = db.scalars(select(BusinessDocument).where(BusinessDocument.business_id == b.id).order_by(BusinessDocument.created_at.desc())).all()
    members = db.scalars(select(BusinessMember).where(BusinessMember.business_id == b.id)).all()
    return {**business_brief(b, ctx.principal.locale), "legal_name": b.legal_name, "cr_number": b.cr_number, "vat_number": b.vat_number,
            "email": b.email, "phone": b.phone, "status": b.status.value, "rejection_reason": b.rejection_reason,
            "created_at": b.created_at, "documents": [{"id": str(d.id), "doc_type": d.doc_type, "number": d.number,
                                                       "expires_on": d.expires_on, "status": d.status.value,
                                                       "file_url": file_url(d.file_id), "review_notes": d.review_notes} for d in docs],
            "members": [{"user_id": str(m.user_id), "name": m.user.full_name, "role": m.role.code, "status": m.status.value} for m in members],
            "branches": [{"name": br.name, "city": city_out(br.city, ctx.principal.locale), "district": br.district} for br in b.branches]}


class VerifyIn(BaseModel):
    decision: Literal["verify", "reject"]
    reason: str | None = Field(default=None, max_length=2000)
    documents: dict[uuid.UUID, Literal["approved", "rejected"]] = {}


@router.post("/businesses/{bid}/verification")
def verify_business(bid: uuid.UUID, data: VerifyIn, request: Request, db: Session = Depends(get_db),
                    ctx: AdminCtx = Depends(admin_ctx("admin.businesses.verify"))):
    b = db.get(Business, bid)
    if b is None:
        raise NotFound()
    for doc_id, st in data.documents.items():
        d = db.get(BusinessDocument, doc_id)
        if d is None or d.business_id != b.id:
            raise ValidationFailed("invalid_document")
        d.status, d.reviewed_by, d.reviewed_at = DocumentStatus(st), ctx.user.id, utcnow()
    if data.decision == "verify":
        if not db.scalar(select(func.count()).select_from(BusinessDocument).where(
                BusinessDocument.business_id == b.id, BusinessDocument.status == DocumentStatus.approved)):
            raise ValidationFailed("approved_document_required")
        b.verification_status, b.verified_at, b.verified_by, b.rejection_reason = VerificationStatus.verified, utcnow(), ctx.user.id, None
        event = "account_verified"
    else:
        if not data.reason:
            raise ValidationFailed("reason_required")
        b.verification_status, b.rejection_reason = VerificationStatus.rejected, data.reason
        event = "account_rejected"
    notify(db, members_with_permission(db, b.id), event, {"name": b.trade_name_ar, "reason": data.reason or ""}, link="/app/business")
    audit(db, f"admin.business_{data.decision}", actor_user_id=ctx.user.id, entity_type="business", entity_id=b.id,
          reason=data.reason, changes={"documents": {str(k): v for k, v in data.documents.items()}}, request=request)
    db.commit()
    return business_detail(bid, db, ctx)


@router.post("/businesses/{bid}/status")
def business_status(bid: uuid.UUID, status: BusinessStatus, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                    ctx: AdminCtx = Depends(admin_ctx("admin.businesses.verify"))):
    b = db.get(Business, bid)
    if b is None:
        raise NotFound()
    b.status = status
    audit(db, "admin.business_status", actor_user_id=ctx.user.id, entity_type="business", entity_id=b.id,
          changes={"status": status.value}, reason=data.reason, request=request)
    db.commit()
    return {"status": b.status.value}


@router.get("/representatives")
def representatives(verification: VerificationStatus | None = None, q: str | None = None, params: PageParams = Depends(),
                    db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.reps.verify"))):
    stmt = select(Representative).order_by(Representative.created_at.desc())
    if verification:
        stmt = stmt.where(Representative.verification_status == verification)
    if q:
        stmt = stmt.where(Representative.display_name.ilike(f"%{q}%"))

    def m(r: Representative):
        docs = db.scalars(select(RepresentativeDocument).where(RepresentativeDocument.representative_id == r.id)).all()
        return {"id": str(r.id), "display_name": r.display_name, "kind": r.kind.value, "verification_status": r.verification_status.value,
                "phone": r.user.phone, "email": r.user.email, "is_active": r.is_active, "created_at": r.created_at,
                "rejection_reason": r.rejection_reason, "freelance_doc_number": r.freelance_doc_number,
                "documents": [{"id": str(d.id), "doc_type": d.doc_type, "status": d.status.value, "file_url": file_url(d.file_id)} for d in docs]}

    return paginate(db, stmt, params, m)


@router.post("/representatives/{rid}/verification")
def verify_rep(rid: uuid.UUID, data: VerifyIn, request: Request, db: Session = Depends(get_db),
               ctx: AdminCtx = Depends(admin_ctx("admin.reps.verify"))):
    r = db.get(Representative, rid)
    if r is None:
        raise NotFound()
    for doc_id, st in data.documents.items():
        d = db.get(RepresentativeDocument, doc_id)
        if d is None or d.representative_id != r.id:
            raise ValidationFailed("invalid_document")
        d.status, d.reviewed_by, d.reviewed_at = DocumentStatus(st), ctx.user.id, utcnow()
    if data.decision == "verify":
        if not db.scalar(select(func.count()).select_from(RepresentativeDocument).where(
                RepresentativeDocument.representative_id == r.id, RepresentativeDocument.status == DocumentStatus.approved)):
            raise ValidationFailed("approved_document_required")
        r.verification_status, r.verified_at, r.rejection_reason = VerificationStatus.verified, utcnow(), None
        event = "account_verified"
    else:
        if not data.reason:
            raise ValidationFailed("reason_required")
        r.verification_status, r.rejection_reason = VerificationStatus.rejected, data.reason
        event = "account_rejected"
    notify(db, [r.user_id], event, {"name": r.display_name, "reason": data.reason or ""}, link="/app/rep/profile")
    audit(db, f"admin.rep_{data.decision}", actor_user_id=ctx.user.id, entity_type="representative", entity_id=r.id,
          reason=data.reason, request=request)
    db.commit()
    return {"verification_status": r.verification_status.value}


@router.post("/representatives/{rid}/active")
def rep_active(rid: uuid.UUID, active: bool, data: ReasonIn, request: Request, db: Session = Depends(get_db),
               ctx: AdminCtx = Depends(admin_ctx("admin.reps.verify"))):
    r = db.get(Representative, rid)
    if r is None:
        raise NotFound()
    r.is_active = active
    audit(db, "admin.rep_active", actor_user_id=ctx.user.id, entity_type="representative", entity_id=r.id,
          changes={"active": active}, reason=data.reason, request=request)
    db.commit()
    return {"is_active": r.is_active}


# ------------------------------------------------------------------ catalog master data
class CategoryIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]{2,60}$")
    name: dict[str, str]
    icon: str | None = Field(default=None, max_length=40)
    parent_id: int | None = None
    sort_order: int = 0
    is_active: bool = True


@router.post("/categories", status_code=201)
def create_category(data: CategoryIn, request: Request, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    if not all(data.name.get(l) for l in SUPPORTED_LOCALES):
        raise ValidationFailed("all_languages_required")
    if db.scalar(select(Category.id).where(Category.slug == data.slug)):
        raise Conflict("category_exists")
    c = Category(**data.model_dump())
    db.add(c)
    audit(db, "admin.category_create", actor_user_id=ctx.user.id, entity_type="category", changes=data.model_dump(), request=request)
    db.commit()
    return {"id": c.id}


@router.put("/categories/{cid}")
def update_category(cid: int, data: CategoryIn, request: Request, db: Session = Depends(get_db),
                    ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    c = db.get(Category, cid)
    if c is None:
        raise NotFound()
    if not all(data.name.get(l) for l in SUPPORTED_LOCALES):
        raise ValidationFailed("all_languages_required")
    for k, v in data.model_dump().items():
        setattr(c, k, v)
    audit(db, "admin.category_update", actor_user_id=ctx.user.id, entity_type="category", entity_id=cid, changes=data.model_dump(), request=request)
    db.commit()
    return {"id": c.id}


@router.get("/products")
def products(q: str | None = None, status: ProductStatus | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
             ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    from app.modules.catalog.router import apply_search, product_out

    stmt = apply_search(select(Product).order_by(Product.created_at.desc()), q)
    if status:
        stmt = stmt.where(Product.status == status)
    page = paginate(db, stmt, params)
    ids = [p.id for p in page["items"]]
    counts = dict(db.execute(select(SupplierProduct.product_id, func.count()).where(SupplierProduct.product_id.in_(ids))
                             .group_by(SupplierProduct.product_id)).all()) if ids else {}
    page["items"] = [{**product_out(p, ctx.principal.locale), "offers": counts.get(p.id, 0)} for p in page["items"]]
    return page


@router.post("/products/{pid}/status")
def product_status(pid: uuid.UUID, status: ProductStatus, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                   ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    p = db.get(Product, pid)
    if p is None:
        raise NotFound()
    p.status = status
    audit(db, "admin.product_status", actor_user_id=ctx.user.id, entity_type="product", entity_id=p.id,
          changes={"status": status.value}, reason=data.reason, request=request)
    db.commit()
    return {"status": p.status.value}


class BrandAdminIn(BaseModel):
    name_ar: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    manufacturer: str | None = None
    is_active: bool = True


@router.put("/brands/{bid}")
def update_brand(bid: uuid.UUID, data: BrandAdminIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    b = db.get(Brand, bid)
    if b is None:
        raise NotFound()
    for k, v in data.model_dump().items():
        setattr(b, k, v)
    db.commit()
    return {"id": str(b.id)}


@router.post("/brands", status_code=201)
def create_brand(data: BrandAdminIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.catalog.manage"))):
    b = Brand(**data.model_dump(), slug=slugify(data.name_en) + "-" + uuid.uuid4().hex[:4])
    db.add(b)
    db.commit()
    return {"id": str(b.id)}


# ------------------------------------------------------------------ orders, commissions
@router.get("/orders")
def orders(status: str | None = None, q: str | None = None, supplier_id: uuid.UUID | None = None, retailer_id: uuid.UUID | None = None,
           params: PageParams = Depends(), db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.orders.view"))):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status.in_(status.split(",")))
    if q:
        stmt = stmt.where(Order.number.ilike(f"%{q}%"))
    if supplier_id:
        stmt = stmt.where(Order.supplier_id == supplier_id)
    if retailer_id:
        stmt = stmt.where(Order.retailer_id == retailer_id)
    return paginate(db, stmt, params, lambda o: order_out(db, o, ctx.principal.locale, "admin"))


@router.get("/orders/{oid}")
def order_detail(oid: uuid.UUID, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.orders.view"))):
    o = db.get(Order, oid)
    if o is None:
        raise NotFound()
    return order_out(db, o, ctx.principal.locale, "admin", detail=True)


@router.get("/commissions")
def commissions(status: CommissionStatus | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
                ctx: AdminCtx = Depends(admin_ctx("admin.commissions.view"))):
    from app.modules.commissions.router import _summary, commission_out

    stmt = select(Commission).order_by(Commission.created_at.desc())
    if status:
        stmt = stmt.where(Commission.status == status)
    page = paginate(db, stmt, params, lambda c: commission_out(db, c, ctx.principal.locale))
    page["summary"] = _summary(db, Commission.id.isnot(None))
    page["open_disputes"] = db.scalar(select(func.count()).select_from(CommissionDispute).where(CommissionDispute.status == "open")) or 0
    return page


# ------------------------------------------------------------------ complaints & disputes
@router.get("/complaints")
def complaints(status: CS | None = None, kind: ComplaintKind | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
               ctx: AdminCtx = Depends(admin_ctx("admin.complaints.manage"))):
    from app.modules.complaints.router import complaint_out

    stmt = select(Complaint).order_by(Complaint.created_at.desc())
    if status:
        stmt = stmt.where(Complaint.status == status)
    if kind:
        stmt = stmt.where(Complaint.kind == kind)
    return paginate(db, stmt, params, lambda c: complaint_out(db, c, ctx.principal.locale, "admin"))


class ComplaintActionIn(BaseModel):
    status: CS | None = None
    message: str | None = Field(default=None, max_length=8000)
    internal: bool = False
    resolution: str | None = Field(default=None, max_length=8000)
    order_outcome: Literal["completed", "cancelled", "restore"] | None = None


@router.post("/complaints/{cid}")
def complaint_action(cid: uuid.UUID, data: ComplaintActionIn, request: Request, db: Session = Depends(get_db),
                     ctx: AdminCtx = Depends(admin_ctx("admin.complaints.manage"))):
    from app.modules.commissions import service as commissions
    from app.modules.complaints.router import complaint_out

    c = db.get(Complaint, cid)
    if c is None:
        raise NotFound()
    c.assigned_admin_id = c.assigned_admin_id or ctx.user.id
    if data.message:
        db.add(ComplaintMessage(complaint_id=c.id, author_user_id=ctx.user.id, author_side="admin", body=data.message, internal=data.internal))
    if data.status:
        c.status = data.status
        if data.status in (CS.resolved, CS.rejected, CS.closed):
            if not data.resolution and data.status != CS.closed:
                raise ValidationFailed("resolution_required")
            c.resolution, c.resolved_at = data.resolution or c.resolution, utcnow()
            if c.kind == ComplaintKind.order_dispute and c.order_id:
                o = db.get(Order, c.order_id)
                if o and o.status == S.disputed:
                    target = {"completed": S.completed, "cancelled": S.cancelled,
                              "restore": S(c.order_status_before or "completed")}[data.order_outcome or "restore"]
                    if target == S.disputed:
                        target = S.completed
                    order_svc.transition(db, o, target, ctx.user.id, "admin", f"dispute {c.number}: {data.resolution or ''}")
                    comm = db.scalar(select(Commission).where(Commission.order_id == o.id))
                    if comm and comm.status == CommissionStatus.disputed:
                        comm.status = CommissionStatus.cancelled if target == S.cancelled else CommissionStatus.pending
                        if target != S.cancelled:
                            comm.due_at = utcnow()
                    if target == S.cancelled:
                        commissions.on_order_event(db, o, "cancelled")
    if not data.internal and (data.message or data.status):
        notify(db, [c.raised_by_user_id], "complaint_reply", {"number": c.number}, link=f"/app/complaints/{c.id}")
    audit(db, "admin.complaint_action", actor_user_id=ctx.user.id, entity_type="complaint", entity_id=c.id,
          changes=data.model_dump(), request=request)
    db.commit()
    db.refresh(c)
    return complaint_out(db, c, ctx.principal.locale, "admin")


# ------------------------------------------------------------------ ratings moderation
@router.get("/ratings")
def ratings(status: RatingStatus = RatingStatus.flagged, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.ratings.moderate"))):
    from app.modules.ratings.router import rating_out

    return [rating_out(r) for r in db.scalars(select(Rating).where(Rating.status == status).order_by(Rating.updated_at.desc()).limit(300))]


@router.post("/ratings/{rid}")
def moderate(rid: uuid.UUID, status: Literal["published", "hidden"], data: ReasonIn, request: Request, db: Session = Depends(get_db),
             ctx: AdminCtx = Depends(admin_ctx("admin.ratings.moderate"))):
    r = db.get(Rating, rid)
    if r is None:
        raise NotFound()
    r.status, r.moderation_note = RatingStatus(status), data.reason
    db.flush()
    refresh_aggregate(db, r.target_type, r.target_id)
    audit(db, "admin.rating_moderate", actor_user_id=ctx.user.id, entity_type="rating", entity_id=r.id, changes={"status": status},
          reason=data.reason, request=request)
    db.commit()
    return {"status": r.status.value}


# ------------------------------------------------------------------ subscriptions & ads
class PlanIn(BaseModel):
    code: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    audience: Literal["supplier", "retailer", "representative"]
    name: dict[str, str]
    price_monthly: Decimal = Field(ge=0)
    price_yearly: Decimal = Field(ge=0)
    limits: dict[str, Any] = {}
    features: list[str] = []
    is_active: bool = True
    sort_order: int = 0


@router.get("/plans")
def plans(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.subscriptions.manage"))):
    return [{"id": str(p.id), "code": p.code, "audience": p.audience, "name": p.name, "price_monthly": p.price_monthly,
             "price_yearly": p.price_yearly, "limits": p.limits, "features": p.features, "is_active": p.is_active}
            for p in db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.audience, SubscriptionPlan.sort_order))]


@router.post("/plans", status_code=201)
def upsert_plan(data: PlanIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.subscriptions.manage"))):
    p = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == data.code))
    if p is None:
        p = SubscriptionPlan(code=data.code, audience=data.audience, name=data.name)
        db.add(p)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"id": str(p.id)}


class SubscriptionIn(BaseModel):
    business_id: uuid.UUID | None = None
    representative_id: uuid.UUID | None = None
    plan_code: str
    status: SubscriptionStatus = SubscriptionStatus.active
    period_end: datetime | None = None
    notes: str | None = None


@router.get("/subscriptions")
def subscriptions(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.subscriptions.manage"))):
    rows = db.scalars(select(Subscription).order_by(Subscription.created_at.desc()).limit(500)).all()
    return [{"id": str(s.id), "business_id": str(s.business_id) if s.business_id else None,
             "representative_id": str(s.representative_id) if s.representative_id else None, "plan": s.plan.code,
             "status": s.status.value, "period_start": s.period_start, "period_end": s.period_end, "notes": s.notes} for s in rows]


@router.post("/subscriptions", status_code=201)
def create_subscription(data: SubscriptionIn, request: Request, db: Session = Depends(get_db),
                        ctx: AdminCtx = Depends(admin_ctx("admin.subscriptions.manage"))):
    plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == data.plan_code))
    if plan is None or (data.business_id is None) == (data.representative_id is None):
        raise ValidationFailed("invalid_subscription")
    s = Subscription(business_id=data.business_id, representative_id=data.representative_id, plan_id=plan.id, status=data.status,
                     period_start=utcnow(), period_end=data.period_end, notes=data.notes)
    db.add(s)
    audit(db, "admin.subscription_create", actor_user_id=ctx.user.id, entity_type="subscription", changes=data.model_dump(), request=request)
    db.commit()
    return {"id": str(s.id)}


class AdIn(BaseModel):
    business_id: uuid.UUID | None = None
    placement: Literal["retailer_dashboard", "marketplace_top", "rep_dashboard", "supplier_dashboard"]
    title: dict[str, str]
    body: dict[str, str] = {}
    link_url: str | None = Field(default=None, max_length=255, pattern=r"^(https://|/)")
    starts_at: datetime
    ends_at: datetime
    status: AdStatus = AdStatus.draft
    city_ids: list[int] = []


def ad_out(a: Advertisement) -> dict:
    return {"id": str(a.id), "business_id": str(a.business_id) if a.business_id else None, "placement": a.placement, "title": a.title,
            "body": a.body, "link_url": a.link_url, "image_url": file_url(a.image_file_id), "starts_at": a.starts_at, "ends_at": a.ends_at,
            "status": a.status.value, "city_ids": a.city_ids, "impressions": a.impressions, "clicks": a.clicks}


@router.get("/ads")
def ads(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.ads.manage"))):
    return [ad_out(a) for a in db.scalars(select(Advertisement).order_by(Advertisement.starts_at.desc()))]


@router.post("/ads", status_code=201)
def create_ad(data: AdIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.ads.manage"))):
    if data.ends_at <= data.starts_at:
        raise ValidationFailed("invalid_dates")
    a = Advertisement(**data.model_dump())
    db.add(a)
    db.commit()
    return ad_out(a)


@router.put("/ads/{aid}")
def update_ad(aid: uuid.UUID, data: AdIn, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.ads.manage"))):
    a = db.get(Advertisement, aid)
    if a is None:
        raise NotFound()
    for k, v in data.model_dump().items():
        setattr(a, k, v)
    db.commit()
    return ad_out(a)


# ------------------------------------------------------------------ content, translations, languages, settings
class PageIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,80}$")
    locale: Literal["ar", "en", "ur", "hi"]
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=10, max_length=200000)
    version: str = Field(default="1.0", max_length=20)
    is_published: bool = True


@router.get("/pages")
def pages(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.content.manage"))):
    return [{"id": str(p.id), "slug": p.slug, "locale": p.locale, "title": p.title, "version": p.version,
             "is_published": p.is_published, "updated_at": p.updated_at}
            for p in db.scalars(select(ContentPage).order_by(ContentPage.slug, ContentPage.locale))]


@router.put("/pages")
def upsert_page(data: PageIn, request: Request, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.content.manage"))):
    p = db.scalar(select(ContentPage).where(ContentPage.slug == data.slug, ContentPage.locale == data.locale))
    if p is None:
        p = ContentPage(slug=data.slug, locale=data.locale, title=data.title, body=data.body)
        db.add(p)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    p.updated_by = ctx.user.id
    audit(db, "admin.page_upsert", actor_user_id=ctx.user.id, entity_type="content_page", entity_id=f"{data.slug}:{data.locale}",
          changes={"version": data.version}, request=request)
    db.commit()
    return {"id": str(p.id)}


class OverrideIn(BaseModel):
    locale: Literal["ar", "en", "ur", "hi"]
    key: str = Field(min_length=2, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
    value: str = Field(max_length=4000)


@router.get("/translations")
def translations(locale: Literal["ar", "en", "ur", "hi"] | None = None, db: Session = Depends(get_db),
                 ctx: AdminCtx = Depends(admin_ctx("admin.translations.manage"))):
    stmt = select(TranslationOverride).order_by(TranslationOverride.locale, TranslationOverride.key)
    if locale:
        stmt = stmt.where(TranslationOverride.locale == locale)
    return {"overrides": [{"id": str(o.id), "locale": o.locale, "key": o.key, "value": o.value, "updated_at": o.updated_at}
                          for o in db.scalars(stmt)],
            "backend_missing": missing_keys(), "backend_keys": len(catalog("ar")),
            "languages": [{"code": l.code, "name": l.native_name, "direction": l.direction, "is_enabled": l.is_enabled}
                          for l in db.scalars(select(Language).order_by(Language.sort_order))]}


@router.put("/translations")
def upsert_translation(data: OverrideIn, request: Request, db: Session = Depends(get_db),
                       ctx: AdminCtx = Depends(admin_ctx("admin.translations.manage"))):
    o = db.scalar(select(TranslationOverride).where(TranslationOverride.locale == data.locale, TranslationOverride.key == data.key))
    if o is None:
        o = TranslationOverride(locale=data.locale, key=data.key, value=data.value)
        db.add(o)
    o.value, o.updated_by = data.value, ctx.user.id
    audit(db, "admin.translation_upsert", actor_user_id=ctx.user.id, entity_type="translation", entity_id=f"{data.locale}:{data.key}",
          request=request)
    db.commit()
    set_overrides(data.locale, {r.key: r.value for r in db.scalars(select(TranslationOverride).where(TranslationOverride.locale == data.locale))})
    return {"ok": True}


@router.delete("/translations/{oid}")
def delete_translation(oid: uuid.UUID, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.translations.manage"))):
    o = db.get(TranslationOverride, oid)
    if o is None:
        raise NotFound()
    loc = o.locale
    db.delete(o)
    db.commit()
    set_overrides(loc, {r.key: r.value for r in db.scalars(select(TranslationOverride).where(TranslationOverride.locale == loc))})
    return {"ok": True}


@router.post("/languages/{code}")
def toggle_language(code: str, enabled: bool, db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.translations.manage"))):
    l = db.get(Language, code)
    if l is None:
        raise NotFound()
    if code == "ar" and not enabled:
        raise Conflict("default_language_required")
    l.is_enabled = enabled
    db.commit()
    return {"code": code, "is_enabled": enabled}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.settings.manage"))):
    return [{"key": s.key, "value": s.value, "is_public": s.is_public, "updated_at": s.updated_at} for s in db.scalars(select(PlatformSetting))]


class SettingIn(BaseModel):
    value: Any
    is_public: bool | None = None


@router.put("/settings/{key}")
def put_setting(key: str, data: SettingIn, request: Request, db: Session = Depends(get_db),
                ctx: AdminCtx = Depends(admin_ctx("admin.settings.manage"))):
    if len(key) > 80 or len(json.dumps(data.value)) > 20000:
        raise ValidationFailed("invalid_setting")
    s = db.get(PlatformSetting, key)
    old = s.value if s else None
    if s is None:
        s = PlatformSetting(key=key, value=data.value, is_public=bool(data.is_public))
        db.add(s)
    s.value, s.updated_by = data.value, ctx.user.id
    if data.is_public is not None:
        s.is_public = data.is_public
    audit(db, "admin.setting", actor_user_id=ctx.user.id, entity_type="setting", entity_id=key, changes={"old": old, "new": data.value},
          request=request)
    db.commit()
    return {"key": key, "value": s.value}


# ------------------------------------------------------------------ audit, system, privacy, contact
@router.get("/audit")
def audit_logs(action: str | None = None, entity_type: str | None = None, entity_id: str | None = None, result: str | None = None,
               actor_user_id: uuid.UUID | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
               ctx: AdminCtx = Depends(admin_ctx("admin.audit.view"))):
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"{action}%"))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if result:
        stmt = stmt.where(AuditLog.result == result)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    return paginate(db, stmt, params, lambda a: {
        "id": a.id, "created_at": a.created_at, "action": a.action, "actor_user_id": str(a.actor_user_id) if a.actor_user_id else None,
        "actor_business_id": str(a.actor_business_id) if a.actor_business_id else None, "entity_type": a.entity_type,
        "entity_id": a.entity_id, "result": a.result, "changes": a.changes, "reason": a.reason, "ip": a.ip, "request_id": a.request_id})


@router.get("/system")
def system(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.system.view"))):
    import redis

    outbox = {s.value: n for s, n in db.execute(select(NotificationDelivery.status, func.count()).group_by(NotificationDelivery.status))}
    jobs = {}
    for name in db.scalars(select(JobRun.job).distinct()):
        last = db.scalar(select(JobRun).where(JobRun.job == name).order_by(JobRun.started_at.desc()).limit(1))
        jobs[name] = {"last_run": last.started_at, "success": last.success, "processed": last.processed, "error": last.error}
    try:
        redis.Redis.from_url(settings.redis_url, socket_timeout=0.5).ping()
        redis_ok = True
    except Exception:  # noqa: BLE001
        redis_ok = False
    db_size = db.execute(text("SELECT pg_database_size(current_database())")).scalar()
    usage = shutil.disk_usage(settings.storage_dir if os.path.exists(settings.storage_dir) else "/")
    from app.integrations.channels import channel_enabled

    return {"database": {"ok": True, "size_bytes": db_size}, "redis": {"ok": redis_ok}, "outbox": outbox, "jobs": jobs,
            "storage": {"total": usage.total, "used": usage.used, "free": usage.free},
            "channels": {c: channel_enabled(c) for c in ("email", "sms", "whatsapp", "push")},
            "ai_provider": settings.ai_provider, "env": settings.env, "version": "1.0.0",
            "failed_deliveries": outbox.get(OutboxStatus.failed.value, 0)}


@router.get("/data-requests")
def data_requests(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.data_requests.manage"))):
    return [{"id": str(r.id), "user_id": str(r.user_id), "kind": r.kind.value, "status": r.status.value, "reason": r.reason,
             "notes": r.notes, "created_at": r.created_at, "handled_at": r.handled_at}
            for r in db.scalars(select(DataRequest).order_by(DataRequest.created_at.desc()).limit(500))]


class DataRequestActionIn(BaseModel):
    status: Literal["processing", "completed", "rejected"]
    notes: str | None = Field(default=None, max_length=4000)


@router.post("/data-requests/{rid}")
def handle_data_request(rid: uuid.UUID, data: DataRequestActionIn, request: Request, db: Session = Depends(get_db),
                        ctx: AdminCtx = Depends(admin_ctx("admin.data_requests.manage"))):
    from app.modules.privacy.service import anonymize_user

    r = db.get(DataRequest, rid)
    if r is None:
        raise NotFound()
    if data.status == "completed" and r.kind.value == "deletion":
        anonymize_user(db, r.user_id)
    r.status, r.notes, r.handled_by, r.handled_at = DataRequestStatus(data.status), data.notes, ctx.user.id, utcnow()
    audit(db, "admin.data_request", actor_user_id=ctx.user.id, entity_type="data_request", entity_id=r.id, changes=data.model_dump(),
          request=request)
    db.commit()
    return {"status": r.status.value}


@router.get("/contact-messages")
def contact_messages(db: Session = Depends(get_db), ctx: AdminCtx = Depends(admin_ctx("admin.dashboard"))):
    return [{"id": str(m.id), "name": m.name, "email": m.email, "phone": m.phone, "audience": m.audience, "message": m.message,
             "handled": m.handled, "created_at": m.created_at}
            for m in db.scalars(select(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(300))]
