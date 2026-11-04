"""Representatives marketplace: professional profiles, verification documents,
directory search for suppliers, company representatives, tasks and targets."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, supplier_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.i18n import localized
from app.core.schemas import PageParams, paginate
from app.core.storage import save_upload
from app.core.utils import mask_phone, normalize_phone, utcnow
from app.models.business import City
from app.models.catalog import Category
from app.models.crm import Customer, Visit
from app.models.enums import (
    AuthorizationStatus,
    Channel,
    CustomerStatus,
    DocumentStatus,
    FilePurpose,
    OrderStatus,
    Priority,
    RepAvailability,
    RepCompanyRelation,
    RepCompanyStatus,
    RepKind,
    TaskStatus,
    UserStatus,
    VerificationPurpose,
    VerificationStatus,
    VisitStatus,
)
from app.models.identity import User
from app.models.orders import Order
from app.models.reps import (
    Authorization,
    Representative,
    RepresentativeArea,
    RepresentativeCategory,
    RepresentativeCompany,
    RepresentativeDocument,
    RepTarget,
    RepTask,
)
from app.modules.common import business_brief, city_out, file_url
from app.modules.notifications.service import notify

router = APIRouter(tags=["representatives"])

COUNTED_STATUSES = [OrderStatus.approved, OrderStatus.preparing, OrderStatus.ready, OrderStatus.out_for_delivery,
                    OrderStatus.delivered, OrderStatus.completed, OrderStatus.partially_returned]


def _cities(db: Session, ids) -> dict[int, City]:
    ids = list(set(ids))
    return {c.id: c for c in db.scalars(select(City).where(City.id.in_(ids)))} if ids else {}


def rep_public(db: Session, r: Representative, locale: str, *, private: bool = False) -> dict:
    cities = _cities(db, [a.city_id for a in r.areas])
    cats = {c.id: c for c in db.scalars(select(Category).where(Category.id.in_([c.category_id for c in r.categories])))} if r.categories else {}
    with system_context(db):
        active_customers = db.scalar(select(func.count(func.distinct(Order.retailer_id))).where(
            Order.representative_id == r.id, Order.status.in_(COUNTED_STATUSES))) or 0
        companies = db.scalar(select(func.count()).select_from(RepresentativeCompany).where(
            RepresentativeCompany.representative_id == r.id, RepresentativeCompany.status == RepCompanyStatus.active)) or 0
    out = {
        "id": str(r.id), "display_name": r.display_name, "kind": r.kind.value, "headline": r.headline, "bio": r.bio,
        "experience_years": r.experience_years, "skills": r.skills, "languages": r.languages,
        "availability": r.availability.value, "verification_status": r.verification_status.value,
        "rating_avg": round(r.rating_avg or 0, 2), "rating_count": r.rating_count,
        "areas": [{"city": city_out(cities.get(a.city_id), locale), "city_id": a.city_id, "district": a.district} for a in r.areas],
        "categories": [{"id": c.category_id, "name": localized(cats[c.category_id].name, locale)} for c in r.categories
                       if c.category_id in cats],
        "active_customers": active_customers, "companies_count": companies,
        "phone_masked": mask_phone(r.user.phone),
    }
    if private:
        out.update({"public_profile": r.public_profile, "freelance_doc_number": r.freelance_doc_number,
                    "home_city_id": r.home_city_id, "rejection_reason": r.rejection_reason, "is_active": r.is_active,
                    "email": r.user.email, "phone": r.user.phone})
    return out


# ------------------------------------------------------------------ own profile
class AreaIn(BaseModel):
    city_id: int
    district: str | None = Field(default=None, max_length=120)


class RepProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=160)
    headline: str | None = Field(default=None, max_length=200)
    bio: str | None = Field(default=None, max_length=4000)
    experience_years: int | None = Field(default=None, ge=0, le=60)
    skills: list[str] | None = Field(default=None, max_length=30)
    languages: list[Literal["ar", "en", "ur", "hi", "bn", "tl", "other"]] | None = None
    availability: RepAvailability | None = None
    public_profile: bool | None = None
    freelance_doc_number: str | None = Field(default=None, max_length=40)
    home_city_id: int | None = None
    areas: list[AreaIn] | None = Field(default=None, max_length=50)
    category_ids: list[int] | None = Field(default=None, max_length=30)


@router.get("/rep/profile")
def get_profile(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return rep_public(db, ctx.rep, ctx.principal.locale, private=True)


@router.patch("/rep/profile")
def update_profile(data: RepProfileIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    r = ctx.rep
    values = data.model_dump(exclude_unset=True)
    areas = values.pop("areas", None)
    cats = values.pop("category_ids", None)
    if "skills" in values and values["skills"] is not None:
        values["skills"] = [s.strip()[:60] for s in values["skills"] if s.strip()]
    for k, v in values.items():
        setattr(r, k, v)
    if areas is not None:
        if any(db.get(City, a["city_id"]) is None for a in areas):
            raise ValidationFailed("invalid_city")
        r.areas.clear()
        db.flush()
        seen = set()
        for a in areas:
            key = (a["city_id"], (a.get("district") or "").strip())
            if key not in seen:
                seen.add(key)
                r.areas.append(RepresentativeArea(city_id=a["city_id"], district=a.get("district")))
    if cats is not None:
        if any(db.get(Category, c) is None for c in cats):
            raise ValidationFailed("invalid_category")
        r.categories.clear()
        db.flush()
        for c in sorted(set(cats)):
            r.categories.append(RepresentativeCategory(category_id=c))
    audit(db, "rep.profile_update", actor_user_id=ctx.user.id, entity_type="representative", entity_id=r.id,
          changes=data.model_dump(exclude_unset=True), request=request)
    db.commit()
    db.refresh(r)
    return rep_public(db, r, ctx.principal.locale, private=True)


@router.get("/rep/documents")
def list_documents(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rows = db.scalars(select(RepresentativeDocument).where(RepresentativeDocument.representative_id == ctx.rep.id)
                      .order_by(RepresentativeDocument.created_at.desc())).all()
    return [{"id": str(d.id), "doc_type": d.doc_type, "status": d.status.value, "review_notes": d.review_notes,
             "file_url": file_url(d.file_id), "created_at": d.created_at} for d in rows]


@router.post("/rep/documents", status_code=201)
def upload_document(request: Request, doc_type: Literal["national_id", "iqama", "freelance_certificate", "other"] = Form(...),
                    file: UploadFile = File(...), db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rec = save_upload(db, file, FilePurpose.rep_document, owner_user_id=ctx.user.id)
    d = RepresentativeDocument(representative_id=ctx.rep.id, doc_type=doc_type, file_id=rec.id)
    db.add(d)
    audit(db, "rep.document_upload", actor_user_id=ctx.user.id, entity_type="representative_document", entity_id=d.id,
          changes={"doc_type": doc_type}, request=request)
    db.commit()
    return {"id": str(d.id), "status": d.status.value}


@router.post("/rep/verification/submit")
def submit_verification(request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    r = ctx.rep
    if r.verification_status in (VerificationStatus.pending, VerificationStatus.verified):
        raise Conflict("verification_already_submitted")
    if not ctx.user.phone_verified_at:
        raise ValidationFailed("phone_verification_required")
    has_id = db.scalar(select(func.count()).select_from(RepresentativeDocument).where(
        RepresentativeDocument.representative_id == r.id, RepresentativeDocument.doc_type.in_(["national_id", "iqama"]),
        RepresentativeDocument.status != DocumentStatus.rejected))
    if not has_id:
        raise ValidationFailed("id_document_required")
    r.verification_status = VerificationStatus.pending
    r.rejection_reason = None
    audit(db, "rep.verification_submit", actor_user_id=ctx.user.id, entity_type="representative", entity_id=r.id, request=request)
    db.commit()
    return {"verification_status": r.verification_status.value}


@router.get("/rep/companies")
def my_companies(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rels = db.scalars(select(RepresentativeCompany).where(RepresentativeCompany.representative_id == ctx.rep.id)).all()
    from app.models.business import Business

    out = []
    for rel in rels:
        sup = db.get(Business, rel.supplier_id)
        auths = db.scalars(select(Authorization).where(Authorization.representative_id == ctx.rep.id,
                                                       Authorization.supplier_id == rel.supplier_id)).all()
        out.append({"supplier": business_brief(sup, ctx.principal.locale), "relation": rel.relation.value,
                    "status": rel.status.value, "employee_code": rel.employee_code, "started_at": rel.started_at,
                    "authorizations": [{"id": str(a.id), "number": a.number, "status": a.status.value,
                                        "end_date": a.end_date} for a in auths]})
    return out


# ------------------------------------------------------------------ directory (suppliers search reps)
@router.get("/market/representatives")
def directory(city_id: int | None = None, category_id: int | None = None, min_experience: int | None = None,
              min_rating: float | None = None, availability: RepAvailability | None = None, kind: RepKind | None = None,
              q: str | None = None, sort: Literal["rating", "experience", "newest"] = "rating",
              params: PageParams = Depends(), db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    stmt = select(Representative).where(Representative.public_profile.is_(True), Representative.is_active.is_(True),
                                        Representative.verification_status == VerificationStatus.verified)
    if city_id:
        stmt = stmt.where(Representative.id.in_(select(RepresentativeArea.representative_id).where(RepresentativeArea.city_id == city_id)))
    if category_id:
        stmt = stmt.where(Representative.id.in_(select(RepresentativeCategory.representative_id).where(
            RepresentativeCategory.category_id == category_id)))
    if min_experience is not None:
        stmt = stmt.where(Representative.experience_years >= min_experience)
    if min_rating is not None:
        stmt = stmt.where(Representative.rating_avg >= min_rating)
    if availability:
        stmt = stmt.where(Representative.availability == availability)
    if kind:
        stmt = stmt.where(Representative.kind == kind)
    if q:
        stmt = stmt.where(or_(Representative.display_name.ilike(f"%{q}%"), Representative.headline.ilike(f"%{q}%")))
    stmt = stmt.order_by({"rating": Representative.rating_avg.desc(), "experience": Representative.experience_years.desc(),
                          "newest": Representative.created_at.desc()}[sort], Representative.id)
    return paginate(db, stmt, params, lambda r: rep_public(db, r, ctx.principal.locale))


@router.get("/market/representatives/{rep_id}")
def directory_profile(rep_id: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    r = db.get(Representative, rep_id)
    linked = r is not None and db.scalar(select(RepresentativeCompany.id).where(
        RepresentativeCompany.representative_id == r.id, RepresentativeCompany.supplier_id == ctx.business_id))
    if r is None or (not r.public_profile and not linked) or (r.verification_status != VerificationStatus.verified and not linked):
        raise NotFound()
    out = rep_public(db, r, ctx.principal.locale)
    if linked:  # contact details only for companies the rep works with
        out["phone"] = r.user.phone
        out["email"] = r.user.email
    return out


# ------------------------------------------------------------------ supplier: my reps & company reps
@router.get("/supplier/reps")
def supplier_reps(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rels = db.scalars(select(RepresentativeCompany).where(RepresentativeCompany.supplier_id == ctx.business_id)).all()
    out = []
    for rel in rels:
        r = rel.representative
        auth = db.scalar(select(Authorization).where(Authorization.representative_id == r.id,
                                                     Authorization.supplier_id == ctx.business_id)
                         .order_by(Authorization.created_at.desc()).limit(1))
        sales = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.supplier_id == ctx.business_id, Order.representative_id == r.id, Order.status.in_(COUNTED_STATUSES)))
        out.append({**rep_public(db, r, ctx.principal.locale), "relation": rel.relation.value, "relation_status": rel.status.value,
                    "employee_code": rel.employee_code, "phone": r.user.phone, "email": r.user.email,
                    "latest_authorization": {"id": str(auth.id), "status": auth.status.value, "number": auth.number,
                                             "end_date": auth.end_date} if auth else None,
                    "sales_total": sales})
    return out


class CompanyRepIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str
    employee_code: str | None = Field(default=None, max_length=40)
    supervisor_user_id: uuid.UUID | None = None


@router.post("/supplier/reps/company", status_code=201)
def add_company_rep(data: CompanyRepIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    from app.core.security import hash_password, new_token
    from app.modules.auth.service import issue_code

    phone = normalize_phone(data.phone)
    if not phone:
        raise ValidationFailed("invalid_phone", fields={"phone": "invalid"})
    with system_context(db):
        user = db.scalar(select(User).where(User.phone == phone))
        if user is None and data.email:
            user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
        created = False
        if user is None:
            user = User(full_name=data.full_name, phone=phone, email=data.email.lower() if data.email else None,
                        password_hash=hash_password(new_token(24)), status=UserStatus.pending, locale=ctx.user.locale)
            db.add(user)
            db.flush()
            created = True
        rep = db.scalar(select(Representative).where(Representative.user_id == user.id))
        if rep is None:
            # employees are vouched for by their company (the company holds their HR records)
            rep = Representative(user_id=user.id, kind=RepKind.company, display_name=data.full_name,
                                 verification_status=VerificationStatus.verified, verified_at=utcnow(), public_profile=False)
            db.add(rep)
            db.flush()
        rel = db.scalar(select(RepresentativeCompany).where(RepresentativeCompany.representative_id == rep.id,
                                                            RepresentativeCompany.supplier_id == ctx.business_id))
        if rel and rel.status == RepCompanyStatus.active:
            raise Conflict("already_linked")
        if rel is None:
            rel = RepresentativeCompany(representative_id=rep.id, supplier_id=ctx.business_id)
            db.add(rel)
        rel.relation, rel.status, rel.employee_code = RepCompanyRelation.employee, RepCompanyStatus.active, data.employee_code
        rel.supervisor_user_id, rel.ended_at = data.supervisor_user_id, None
        db.flush()
        if created:
            if user.email:
                issue_code(db, user, Channel.email, VerificationPurpose.reset_password, ttl_minutes=60 * 72)
            else:
                issue_code(db, user, Channel.sms, VerificationPurpose.reset_password, ttl_minutes=60 * 24)
        notify(db, [user.id], "team_invite", {"business": ctx.business.trade_name_ar, "role": "representative"}, link="/app/rep")
    audit(db, "supplier.company_rep_add", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="representative", entity_id=rep.id, changes={"employee_code": data.employee_code}, request=request)
    db.commit()
    return {"representative_id": str(rep.id), "user_created": created}


@router.post("/supplier/reps/{rep_id}/end")
def end_relation(rep_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    from app.modules.authorizations.service import transition

    rel = db.scalar(select(RepresentativeCompany).where(RepresentativeCompany.representative_id == rep_id,
                                                        RepresentativeCompany.supplier_id == ctx.business_id))
    if rel is None:
        raise NotFound()
    rel.status, rel.ended_at = RepCompanyStatus.ended, utcnow()
    for a in db.scalars(select(Authorization).where(Authorization.representative_id == rep_id,
                                                    Authorization.supplier_id == ctx.business_id,
                                                    Authorization.status.in_([AuthorizationStatus.active, AuthorizationStatus.suspended,
                                                                              AuthorizationStatus.pending_rep]))):
        transition(db, a, AuthorizationStatus.cancelled, ctx.user.id, "relation_ended", "relationship ended")
    audit(db, "supplier.rep_relation_end", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="representative", entity_id=rep_id, request=request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ tasks & targets
class TaskIn(BaseModel):
    representative_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    customer_id: uuid.UUID | None = None
    due_at: datetime | None = None
    priority: Priority = Priority.normal


def task_out(t: RepTask) -> dict:
    return {"id": str(t.id), "supplier_id": str(t.supplier_id), "representative_id": str(t.representative_id),
            "customer_id": str(t.customer_id) if t.customer_id else None, "title": t.title, "description": t.description,
            "due_at": t.due_at, "priority": t.priority.value, "status": t.status.value, "completed_at": t.completed_at,
            "created_at": t.created_at}


def _linked_rep(db: Session, supplier_id, rep_id) -> Representative:
    rel = db.scalar(select(RepresentativeCompany).where(RepresentativeCompany.representative_id == rep_id,
                                                        RepresentativeCompany.supplier_id == supplier_id,
                                                        RepresentativeCompany.status == RepCompanyStatus.active))
    if rel is None:
        raise ValidationFailed("representative_not_linked")
    return rel.representative


@router.get("/supplier/tasks")
def supplier_tasks(status: TaskStatus | None = None, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    stmt = select(RepTask).where(RepTask.supplier_id == ctx.business_id).order_by(RepTask.created_at.desc()).limit(500)
    if status:
        stmt = stmt.where(RepTask.status == status)
    return [task_out(t) for t in db.scalars(stmt)]


@router.post("/supplier/tasks", status_code=201)
def create_task(data: TaskIn, request: Request, db: Session = Depends(get_db),
                ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    rep = _linked_rep(db, ctx.business_id, data.representative_id)
    if data.customer_id:
        c = db.get(Customer, data.customer_id)
        if c is None or c.owner_supplier_id != ctx.business_id:
            raise ValidationFailed("invalid_customer")
    t = RepTask(supplier_id=ctx.business_id, created_by=ctx.user.id, **data.model_dump())
    db.add(t)
    notify(db, [rep.user_id], "task_assigned", {"title": data.title, "supplier": ctx.business.trade_name_ar}, link="/app/rep/tasks")
    audit(db, "task.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="rep_task",
          entity_id=t.id, request=request)
    db.commit()
    return task_out(t)


class TaskStatusIn(BaseModel):
    status: TaskStatus


@router.get("/rep/tasks")
def rep_tasks(status: TaskStatus | None = None, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    stmt = select(RepTask).where(RepTask.representative_id == ctx.rep.id).order_by(RepTask.due_at.asc().nulls_last()).limit(500)
    if status:
        stmt = stmt.where(RepTask.status == status)
    return [task_out(t) for t in db.scalars(stmt)]


@router.patch("/rep/tasks/{task_id}")
def rep_task_status(task_id: uuid.UUID, data: TaskStatusIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    t = db.get(RepTask, task_id)
    if t is None or t.representative_id != ctx.rep.id:
        raise NotFound()
    t.status = data.status
    t.completed_at = utcnow() if data.status == TaskStatus.done else None
    db.commit()
    return task_out(t)


@router.patch("/supplier/tasks/{task_id}")
def supplier_task_status(task_id: uuid.UUID, data: TaskStatusIn, db: Session = Depends(get_db),
                         ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    t = db.get(RepTask, task_id)
    if t is None or t.supplier_id != ctx.business_id:
        raise NotFound()
    t.status = data.status
    t.completed_at = utcnow() if data.status == TaskStatus.done else None
    db.commit()
    return task_out(t)


class TargetIn(BaseModel):
    representative_id: uuid.UUID
    period_start: date
    period_end: date
    sales_target: Decimal = Field(ge=0)
    visits_target: int = Field(default=0, ge=0)
    new_customers_target: int = Field(default=0, ge=0)


def target_progress(db: Session, t: RepTarget) -> dict:
    start = datetime.combine(t.period_start, datetime.min.time())
    end = datetime.combine(t.period_end, datetime.max.time())
    with system_context(db):
        sales = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.supplier_id == t.supplier_id, Order.representative_id == t.representative_id,
            Order.status.in_(COUNTED_STATUSES), Order.approved_at.between(start, end))) or 0
        visits = db.scalar(select(func.count()).select_from(Visit).where(
            Visit.representative_id == t.representative_id, Visit.supplier_id == t.supplier_id,
            Visit.status == VisitStatus.completed, Visit.ended_at.between(start, end))) or 0
        from app.models.crm import CustomerAcquisition

        new_customers = db.scalar(select(func.count()).select_from(CustomerAcquisition).where(
            CustomerAcquisition.supplier_id == t.supplier_id, CustomerAcquisition.representative_id == t.representative_id,
            CustomerAcquisition.acquired_at.between(start, end))) or 0
    return {"id": str(t.id), "representative_id": str(t.representative_id), "supplier_id": str(t.supplier_id),
            "period_start": t.period_start, "period_end": t.period_end, "sales_target": t.sales_target,
            "visits_target": t.visits_target, "new_customers_target": t.new_customers_target,
            "sales_actual": sales, "visits_actual": visits, "new_customers_actual": new_customers}


@router.get("/supplier/targets")
def supplier_targets(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(RepTarget).where(RepTarget.supplier_id == ctx.business_id).order_by(RepTarget.period_start.desc())).all()
    return [target_progress(db, t) for t in rows]


@router.post("/supplier/targets", status_code=201)
def create_target(data: TargetIn, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.reps.manage"))):
    _linked_rep(db, ctx.business_id, data.representative_id)
    if data.period_end < data.period_start:
        raise ValidationFailed("invalid_dates")
    t = RepTarget(supplier_id=ctx.business_id, **data.model_dump())
    db.add(t)
    db.commit()
    return target_progress(db, t)


@router.get("/rep/targets")
def rep_targets(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rows = db.scalars(select(RepTarget).where(RepTarget.representative_id == ctx.rep.id).order_by(RepTarget.period_start.desc())).all()
    return [target_progress(db, t) for t in rows]


__all__ = ["router", "and_", "CustomerStatus"]
