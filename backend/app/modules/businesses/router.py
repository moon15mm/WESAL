"""Business profile, verification documents, team & roles, branches, addresses, coverage."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, retailer_ctx, supplier_ctx
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.i18n import localized
from app.core.rbac import OWNER_ROLE, PERMISSIONS
from app.core.storage import save_upload
from app.core.utils import normalize_phone, utcnow
from app.models.business import Branch, BusinessAddress, BusinessDocument, BusinessMember, City, CoverageArea
from app.models.enums import (
    Channel,
    DocumentStatus,
    FilePurpose,
    MemberStatus,
    RoleScope,
    UserStatus,
    VerificationPurpose,
    VerificationStatus,
)
from app.models.identity import Role, RolePermission, User
from app.modules.common import any_business_ctx, business_brief, city_out, file_url
from app.modules.notifications.service import notify

router = APIRouter(tags=["business"])

DOC_TYPES = ("commercial_registration", "vat_certificate", "municipal_license", "national_address", "other")


class ProfileIn(BaseModel):
    trade_name_ar: str | None = Field(default=None, min_length=2, max_length=200)
    trade_name_en: str | None = Field(default=None, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    cr_number: str | None = Field(default=None, pattern=r"^\d{10}$")
    vat_number: str | None = Field(default=None, pattern=r"^3\d{13}3$")
    activity: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    email: EmailStr | None = None
    phone: str | None = None
    website: str | None = Field(default=None, max_length=200, pattern=r"^https?://")
    city_id: int | None = None
    min_order_value: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    supply_terms: str | None = Field(default=None, max_length=4000)
    payment_terms: str | None = Field(default=None, max_length=4000)
    default_lead_time_days: int | None = Field(default=None, ge=0, le=60)
    discoverable: bool | None = None
    store_type: Literal["grocery", "minimarket", "supermarket", "hypermarket", "pharmacy", "other"] | None = None


def profile_out(ctx: BusinessCtx, db: Session) -> dict:
    b = ctx.business
    locale = ctx.principal.locale
    out = business_brief(b, locale)
    out.update({
        "legal_name": b.legal_name, "cr_number": b.cr_number, "vat_number": b.vat_number, "vat_registered": b.vat_registered,
        "activity": b.activity, "description": b.description, "email": b.email, "phone": b.phone, "website": b.website,
        "min_order_value": b.min_order_value, "supply_terms": b.supply_terms, "payment_terms": b.payment_terms,
        "default_lead_time_days": b.default_lead_time_days, "discoverable": b.discoverable, "store_type": b.store_type,
        "status": b.status.value, "rejection_reason": b.rejection_reason, "verified_at": b.verified_at,
        "my_role": ctx.member.role.code, "my_permissions": sorted(ctx.perms),
    })
    return out


@router.get("/business/profile")
def get_profile(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx())):
    return profile_out(ctx, db)


@router.patch("/business/profile")
def update_profile(data: ProfileIn, request: Request, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    b = ctx.business
    changes = data.model_dump(exclude_unset=True)
    if "phone" in changes and changes["phone"]:
        changes["phone"] = normalize_phone(changes["phone"])
        if not changes["phone"]:
            raise ValidationFailed("invalid_phone", fields={"phone": "invalid"})
    if "city_id" in changes and changes["city_id"] is not None and db.get(City, changes["city_id"]) is None:
        raise ValidationFailed("invalid_city")
    # identity fields of a verified business require re-verification
    identity_changed = any(k in changes and changes[k] != getattr(b, k) for k in ("cr_number", "legal_name", "vat_number"))
    for k, v in changes.items():
        setattr(b, k, v)
    if "vat_number" in changes:
        b.vat_registered = bool(changes["vat_number"])
    if identity_changed and b.verification_status == VerificationStatus.verified:
        b.verification_status = VerificationStatus.pending
    audit(db, "business.update", actor_user_id=ctx.user.id, actor_business_id=b.id, entity_type="business",
          entity_id=b.id, changes=changes, request=request)
    db.commit()
    return profile_out(ctx, db)


@router.post("/business/logo")
def upload_logo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    rec = save_upload(db, file, FilePurpose.business_logo, owner_user_id=ctx.user.id, business_id=ctx.business_id)
    ctx.business.logo_file_id = rec.id
    db.commit()
    return {"logo_url": file_url(rec.id)}


@router.get("/business/documents")
def list_documents(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx())):
    rows = db.scalars(select(BusinessDocument).where(BusinessDocument.business_id == ctx.business_id)
                      .order_by(BusinessDocument.created_at.desc())).all()
    return [{"id": str(d.id), "doc_type": d.doc_type, "number": d.number, "expires_on": d.expires_on,
             "status": d.status.value, "review_notes": d.review_notes, "file_url": file_url(d.file_id),
             "created_at": d.created_at} for d in rows]


@router.post("/business/documents", status_code=201)
def upload_document(request: Request, doc_type: str = Form(...), number: str | None = Form(None),
                    expires_on: date | None = Form(None), file: UploadFile = File(...), db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    if doc_type not in DOC_TYPES:
        raise ValidationFailed("invalid_document_type", fields={"doc_type": "invalid"})
    rec = save_upload(db, file, FilePurpose.business_document, owner_user_id=ctx.user.id, business_id=ctx.business_id)
    doc = BusinessDocument(business_id=ctx.business_id, doc_type=doc_type, file_id=rec.id, number=number, expires_on=expires_on)
    db.add(doc)
    audit(db, "business.document_upload", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="business_document", entity_id=doc.id, changes={"doc_type": doc_type}, request=request)
    db.commit()
    return {"id": str(doc.id), "status": doc.status.value}


@router.post("/business/verification/submit")
def submit_verification(request: Request, db: Session = Depends(get_db),
                        ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    b = ctx.business
    if b.verification_status in (VerificationStatus.pending, VerificationStatus.verified):
        raise Conflict("verification_already_submitted")
    if not b.cr_number:
        raise ValidationFailed("cr_number_required", fields={"cr_number": "required"})
    has_cr = db.scalar(select(func.count()).select_from(BusinessDocument).where(
        BusinessDocument.business_id == b.id, BusinessDocument.doc_type == "commercial_registration",
        BusinessDocument.status != DocumentStatus.rejected))
    if not has_cr:
        raise ValidationFailed("cr_document_required")
    b.verification_status = VerificationStatus.pending
    b.rejection_reason = None
    audit(db, "business.verification_submit", actor_user_id=ctx.user.id, actor_business_id=b.id,
          entity_type="business", entity_id=b.id, request=request)
    db.commit()
    return {"verification_status": b.verification_status.value}


# ------------------------------------------------------------------ team & roles
class MemberIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = None
    role_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=120)


class MemberUpdateIn(BaseModel):
    role_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    status: Literal["active", "disabled"] | None = None
    title: str | None = Field(default=None, max_length=120)


class RoleIn(BaseModel):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    name_ar: str = Field(min_length=2, max_length=80)
    name_en: str = Field(min_length=2, max_length=80)
    permissions: list[str]


def _scope(ctx: BusinessCtx) -> RoleScope:
    return RoleScope(ctx.business.type.value)


def _assignable_role(db: Session, ctx: BusinessCtx, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if role is None or role.scope != _scope(ctx) or (role.business_id not in (None, ctx.business_id)):
        raise ValidationFailed("invalid_role", fields={"role_id": "invalid"})
    return role


@router.get("/business/roles")
def list_roles(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx())):
    rows = db.scalars(select(Role).where(Role.scope == _scope(ctx),
                                         (Role.business_id.is_(None)) | (Role.business_id == ctx.business_id))).all()
    loc = ctx.principal.locale
    return {"roles": [{"id": str(r.id), "code": r.code, "name": localized(r.name, loc), "is_system": r.is_system,
                       "permissions": sorted(r.permission_codes)} for r in rows],
            "available_permissions": PERMISSIONS[_scope(ctx)]}


@router.post("/business/roles", status_code=201)
def create_role(data: RoleIn, request: Request, db: Session = Depends(get_db),
                ctx: BusinessCtx = Depends(any_business_ctx("team.manage"))):
    allowed = set(PERMISSIONS[_scope(ctx)])
    bad = [p for p in data.permissions if p not in allowed]
    if bad or not data.permissions:
        raise ValidationFailed("invalid_permissions", params={"permissions": ",".join(bad)})
    if db.scalar(select(Role.id).where(Role.code == data.code, Role.business_id == ctx.business_id)):
        raise Conflict("role_exists")
    role = Role(code=data.code, scope=_scope(ctx), name={"ar": data.name_ar, "en": data.name_en, "ur": data.name_en,
                                                          "hi": data.name_en},
                is_system=False, business_id=ctx.business_id)
    db.add(role)
    db.flush()
    for p in sorted(set(data.permissions)):
        db.add(RolePermission(role_id=role.id, permission_code=p))
    audit(db, "business.role_create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="role", entity_id=role.id, changes=data.model_dump(), request=request)
    db.commit()
    return {"id": str(role.id)}


def member_out(m: BusinessMember, locale: str) -> dict:
    return {"id": str(m.id), "user_id": str(m.user_id), "full_name": m.user.full_name, "email": m.user.email,
            "phone": m.user.phone, "role_id": str(m.role_id), "role": m.role.code, "role_name": localized(m.role.name, locale),
            "branch_id": str(m.branch_id) if m.branch_id else None, "status": m.status.value, "title": m.title,
            "user_status": m.user.status.value, "created_at": m.created_at}


@router.get("/business/team")
def list_team(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx())):
    rows = db.scalars(select(BusinessMember).where(BusinessMember.business_id == ctx.business_id)
                      .order_by(BusinessMember.created_at)).all()
    return [member_out(m, ctx.principal.locale) for m in rows]


@router.post("/business/team", status_code=201)
def add_member(data: MemberIn, request: Request, db: Session = Depends(get_db),
               ctx: BusinessCtx = Depends(any_business_ctx("team.manage"))):
    from app.core.security import hash_password, new_token
    from app.modules.auth.service import issue_code

    role = _assignable_role(db, ctx, data.role_id)
    if role.code == OWNER_ROLE[_scope(ctx)] and ctx.member.role.code != role.code:
        raise Forbidden("cannot_grant_owner")
    email = data.email.lower() if data.email else None
    phone = normalize_phone(data.phone) if data.phone else None
    if not email and not phone:
        raise ValidationFailed("identifier_required")
    if data.branch_id:
        br = db.get(Branch, data.branch_id)
        if br is None or br.business_id != ctx.business_id:
            raise ValidationFailed("invalid_branch")
    with system_context(db):
        user = None
        if email:
            user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None and phone:
            user = db.scalar(select(User).where(User.phone == phone))
        invited = False
        if user is None:
            user = User(email=email, phone=phone, full_name=data.full_name, password_hash=hash_password(new_token(24)),
                        status=UserStatus.pending, locale=ctx.user.locale)
            db.add(user)
            db.flush()
            invited = True
        if db.scalar(select(BusinessMember.id).where(BusinessMember.business_id == ctx.business_id,
                                                     BusinessMember.user_id == user.id)):
            raise Conflict("already_member")
        m = BusinessMember(business_id=ctx.business_id, user_id=user.id, role_id=role.id, branch_id=data.branch_id,
                           title=data.title, invited_by=ctx.user.id, status=MemberStatus.active)
        db.add(m)
        db.flush()
        if invited and email:
            issue_code(db, user, Channel.email, VerificationPurpose.reset_password, ttl_minutes=60 * 72)
        notify(db, [user.id], "team_invite", {"business": ctx.business.display_name(user.locale), "role": localized(role.name, user.locale)},
               link="/app")
    audit(db, "business.member_add", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="member", entity_id=m.id, changes={"user_id": user.id, "role": role.code}, request=request)
    db.commit()
    db.refresh(m)
    return member_out(m, ctx.principal.locale)


@router.patch("/business/team/{member_id}")
def update_member(member_id: uuid.UUID, data: MemberUpdateIn, request: Request, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(any_business_ctx("team.manage"))):
    m = db.get(BusinessMember, member_id)
    if m is None or m.business_id != ctx.business_id:
        raise NotFound()
    owner_code = OWNER_ROLE[_scope(ctx)]
    changes = data.model_dump(exclude_unset=True)
    new_role = _assignable_role(db, ctx, changes["role_id"]) if changes.get("role_id") else m.role
    new_status = MemberStatus(changes["status"]) if changes.get("status") else m.status
    if new_role.code == owner_code and m.role.code != owner_code and ctx.member.role.code != owner_code:
        raise Forbidden("cannot_grant_owner")
    if m.user_id == ctx.user.id and new_status == MemberStatus.disabled:
        raise Conflict("cannot_disable_self")
    if m.role.code == owner_code and (new_role.code != owner_code or new_status != MemberStatus.active):
        # never leave a business without an active owner
        other_owners = db.scalar(select(func.count()).select_from(BusinessMember).join(Role, Role.id == BusinessMember.role_id)
                                 .where(BusinessMember.business_id == ctx.business_id, Role.code == owner_code,
                                        BusinessMember.status == MemberStatus.active, BusinessMember.id != m.id))
        if not other_owners:
            raise Conflict("last_owner")
    m.role_id = new_role.id
    m.status = new_status
    if "branch_id" in changes:
        if changes["branch_id"]:
            br = db.get(Branch, changes["branch_id"])
            if br is None or br.business_id != ctx.business_id:
                raise ValidationFailed("invalid_branch")
        m.branch_id = changes["branch_id"]
    if "title" in changes:
        m.title = changes["title"]
    audit(db, "business.member_update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="member", entity_id=m.id, changes=changes, request=request)
    db.commit()
    db.refresh(m)
    return member_out(m, ctx.principal.locale)


# ------------------------------------------------------------------ addresses
class AddressIn(BaseModel):
    kind: Literal["headquarters", "warehouse", "billing"] = "headquarters"
    city_id: int | None = None
    district: str | None = Field(default=None, max_length=120)
    address_line: str = Field(min_length=3, max_length=255)
    postal_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    building_number: str | None = Field(default=None, pattern=r"^\d{4}$")
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.get("/business/addresses")
def list_addresses(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx())):
    rows = db.scalars(select(BusinessAddress).where(BusinessAddress.business_id == ctx.business_id)).all()
    return [{"id": str(a.id), "kind": a.kind, "city_id": a.city_id, "district": a.district, "address_line": a.address_line,
             "postal_code": a.postal_code, "building_number": a.building_number, "lat": a.lat, "lng": a.lng} for a in rows]


@router.post("/business/addresses", status_code=201)
def add_address(data: AddressIn, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    a = BusinessAddress(business_id=ctx.business_id, **data.model_dump())
    db.add(a)
    db.commit()
    return {"id": str(a.id)}


@router.delete("/business/addresses/{address_id}")
def delete_address(address_id: uuid.UUID, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(any_business_ctx("business.manage"))):
    a = db.get(BusinessAddress, address_id)
    if a is None or a.business_id != ctx.business_id:
        raise NotFound()
    db.delete(a)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ retailer branches
class BranchIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str | None = Field(default=None, max_length=30)
    city_id: int | None = None
    district: str | None = Field(default=None, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = None
    working_hours: dict | None = None
    manager_user_id: uuid.UUID | None = None
    is_active: bool | None = None


def branch_out(b: Branch, locale: str) -> dict:
    return {"id": str(b.id), "name": b.name, "code": b.code, "city": city_out(b.city, locale), "city_id": b.city_id,
            "district": b.district, "address_line": b.address_line, "lat": b.lat, "lng": b.lng, "phone": b.phone,
            "working_hours": b.working_hours, "manager_user_id": str(b.manager_user_id) if b.manager_user_id else None,
            "is_active": b.is_active, "is_primary": b.is_primary}


@router.get("/retailer/branches")
def list_branches(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx())):
    rows = db.scalars(select(Branch).where(Branch.business_id == ctx.business_id).order_by(Branch.is_primary.desc(), Branch.name)).all()
    return [branch_out(b, ctx.principal.locale) for b in rows]


def _validate_branch(db: Session, ctx: BusinessCtx, data: BranchIn) -> dict:
    values = data.model_dump(exclude_unset=True)
    if values.get("phone"):
        values["phone"] = normalize_phone(values["phone"])
        if not values["phone"]:
            raise ValidationFailed("invalid_phone", fields={"phone": "invalid"})
    if values.get("city_id") is not None and db.get(City, values["city_id"]) is None:
        raise ValidationFailed("invalid_city")
    if values.get("manager_user_id"):
        ok = db.scalar(select(BusinessMember.id).where(BusinessMember.business_id == ctx.business_id,
                                                       BusinessMember.user_id == values["manager_user_id"]))
        if not ok:
            raise ValidationFailed("invalid_manager")
    return values


@router.post("/retailer/branches", status_code=201)
def create_branch(data: BranchIn, request: Request, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(retailer_ctx("retailer.branches.manage"))):
    values = _validate_branch(db, ctx, data)
    values.pop("is_active", None)
    b = Branch(business_id=ctx.business_id, **values)
    db.add(b)
    audit(db, "branch.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="branch",
          entity_id=b.id, changes=values, request=request)
    db.commit()
    return branch_out(b, ctx.principal.locale)


@router.patch("/retailer/branches/{branch_id}")
def update_branch(branch_id: uuid.UUID, data: BranchIn, request: Request, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(retailer_ctx("retailer.branches.manage"))):
    b = db.get(Branch, branch_id)
    if b is None or b.business_id != ctx.business_id:
        raise NotFound()
    values = _validate_branch(db, ctx, data)
    if values.get("is_active") is False and b.is_primary:
        raise Conflict("cannot_deactivate_primary_branch")
    for k, v in values.items():
        setattr(b, k, v)
    audit(db, "branch.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="branch",
          entity_id=b.id, changes=values, request=request)
    db.commit()
    return branch_out(b, ctx.principal.locale)


# ------------------------------------------------------------------ supplier coverage
class CoverageIn(BaseModel):
    city_id: int
    district: str | None = Field(default=None, max_length=120)
    delivery_fee: Decimal = Field(default=Decimal("0"), ge=0, le=100000)
    min_order_value: Decimal | None = Field(default=None, ge=0)
    lead_time_days: int = Field(default=1, ge=0, le=60)
    delivery_days: list[int] | None = None
    is_active: bool = True


@router.get("/supplier/coverage")
def get_coverage(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(CoverageArea).where(CoverageArea.supplier_id == ctx.business_id)).all()
    return [{"id": str(c.id), "city": city_out(c.city, ctx.principal.locale), "city_id": c.city_id, "district": c.district,
             "delivery_fee": c.delivery_fee, "min_order_value": c.min_order_value, "lead_time_days": c.lead_time_days,
             "delivery_days": c.delivery_days, "is_active": c.is_active} for c in rows]


@router.put("/supplier/coverage")
def set_coverage(data: list[CoverageIn], request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.coverage.manage"))):
    if len(data) > 500:
        raise ValidationFailed("too_many_items")
    seen = set()
    for c in data:
        if db.get(City, c.city_id) is None:
            raise ValidationFailed("invalid_city", params={"city_id": c.city_id})
        if c.delivery_days and any(d < 0 or d > 6 for d in c.delivery_days):
            raise ValidationFailed("invalid_delivery_days")
        key = (c.city_id, (c.district or "").strip().lower())
        if key in seen:
            raise ValidationFailed("duplicate_coverage")
        seen.add(key)
    for old in db.scalars(select(CoverageArea).where(CoverageArea.supplier_id == ctx.business_id)).all():
        db.delete(old)
    db.flush()
    for c in data:
        db.add(CoverageArea(supplier_id=ctx.business_id, **c.model_dump()))
    audit(db, "supplier.coverage_set", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          changes={"areas": len(data)}, request=request)
    db.commit()
    return get_coverage(db, ctx)
