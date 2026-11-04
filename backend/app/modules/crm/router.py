"""CRM for suppliers and representatives: customers, contacts, notes, opportunities,
acquisition source (with controlled changes) and store discovery for representatives."""
from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, supplier_ctx
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.schemas import PageParams, paginate
from app.core.utils import normalize_phone, utcnow
from app.models.business import Branch, Business, City
from app.models.crm import (
    Customer,
    CustomerAcquisition,
    CustomerAssignment,
    CustomerContact,
    CustomerNote,
    CustomerSourceChange,
    Opportunity,
    Visit,
)
from app.models.enums import (
    AcquisitionSource,
    BusinessStatus,
    BusinessType,
    CustomerStatus,
    OpportunityStage,
    OrderStatus,
    RepCompanyStatus,
)
from app.models.identity import User
from app.models.orders import Order, OrderItem
from app.models.reps import RepresentativeArea, RepresentativeCompany
from app.modules.common import city_out
from app.modules.crm.service import Owner

router = APIRouter(tags=["crm"])


def customer_out(db: Session, c: Customer, locale: str, detail: bool = False) -> dict:
    out = {
        "id": str(c.id), "name": c.name, "contact_name": c.contact_name, "phone": c.phone, "email": c.email,
        "retailer_id": str(c.retailer_id) if c.retailer_id else None, "registered": c.retailer_id is not None,
        "branch_id": str(c.branch_id) if c.branch_id else None, "city": city_out(c.city, locale), "city_id": c.city_id,
        "district": c.district, "address_line": c.address_line, "lat": c.lat, "lng": c.lng, "status": c.status.value,
        "source": c.source.value, "tags": c.tags,
        "assigned_representative_id": str(c.assigned_representative_id) if c.assigned_representative_id else None,
        "last_order_at": c.last_order_at, "last_visit_at": c.last_visit_at, "next_follow_up_at": c.next_follow_up_at,
        "orders_count": c.orders_count, "total_sales": c.total_sales, "created_at": c.created_at,
    }
    if detail:
        contacts = db.scalars(select(CustomerContact).where(CustomerContact.customer_id == c.id)).all()
        notes = db.scalars(select(CustomerNote).where(CustomerNote.customer_id == c.id).order_by(CustomerNote.created_at.desc()).limit(100)).all()
        authors = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({n.author_user_id for n in notes})))} if notes else {}
        visits = db.scalars(select(Visit).where(Visit.customer_id == c.id).order_by(Visit.created_at.desc()).limit(50)).all()
        opps = db.scalars(select(Opportunity).where(Opportunity.customer_id == c.id).order_by(Opportunity.created_at.desc())).all()
        out["contacts"] = [{"id": str(x.id), "name": x.name, "role": x.role, "phone": x.phone, "email": x.email} for x in contacts]
        out["notes"] = [{"id": str(n.id), "body": n.body, "author": authors.get(n.author_user_id), "created_at": n.created_at} for n in notes]
        out["visits"] = [{"id": str(v.id), "status": v.status.value, "purpose": v.purpose.value,
                          "outcome": v.outcome.value if v.outcome else None, "scheduled_at": v.scheduled_at,
                          "started_at": v.started_at, "ended_at": v.ended_at, "notes": v.notes} for v in visits]
        out["opportunities"] = [opp_out(o) for o in opps]
        out["orders"] = []
        out["favorite_products"] = []
        if c.retailer_id:
            stmt = select(Order).where(Order.retailer_id == c.retailer_id).order_by(Order.created_at.desc()).limit(50)
            stmt = stmt.where(Order.supplier_id == c.owner_supplier_id) if c.owner_supplier_id else \
                stmt.where(Order.representative_id == c.owner_representative_id)
            orders = db.scalars(stmt).all()
            out["orders"] = [{"id": str(o.id), "number": o.number, "status": o.status.value, "total": o.total,
                              "created_at": o.created_at} for o in orders]
            if orders:
                fav = db.execute(select(OrderItem.product_id, func.max(OrderItem.name_ar), func.max(OrderItem.name_en),
                                        func.sum(OrderItem.quantity)).where(OrderItem.order_id.in_([o.id for o in orders]))
                                 .group_by(OrderItem.product_id).order_by(func.sum(OrderItem.quantity).desc()).limit(10)).all()
                out["favorite_products"] = [{"product_id": str(p), "name": ar if locale == "ar" else en, "quantity": int(q)}
                                            for p, ar, en, q in fav]
            if c.owner_supplier_id:
                acq = db.scalar(select(CustomerAcquisition).where(CustomerAcquisition.supplier_id == c.owner_supplier_id,
                                                                  CustomerAcquisition.retailer_id == c.retailer_id))
                if acq:
                    changes = db.scalars(select(CustomerSourceChange).where(CustomerSourceChange.acquisition_id == acq.id)
                                         .order_by(CustomerSourceChange.created_at)).all()
                    out["acquisition"] = {"id": str(acq.id), "source": acq.source.value, "acquired_at": acq.acquired_at,
                                          "representative_id": str(acq.representative_id) if acq.representative_id else None,
                                          "first_order_id": str(acq.first_order_id) if acq.first_order_id else None,
                                          "changes": [{"old_source": x.old_source, "new_source": x.new_source, "reason": x.reason,
                                                       "created_at": x.created_at} for x in changes]}
    return out


def opp_out(o: Opportunity) -> dict:
    return {"id": str(o.id), "customer_id": str(o.customer_id), "title": o.title, "estimated_value": o.estimated_value,
            "stage": o.stage.value, "expected_close_at": o.expected_close_at, "notes": o.notes,
            "supplier_id": str(o.supplier_id) if o.supplier_id else None, "created_at": o.created_at}


class CustomerIn(BaseModel):
    retailer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = None
    email: EmailStr | None = None
    city_id: int | None = None
    district: str | None = Field(default=None, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    tags: list[str] = Field(default=[], max_length=20)
    source: Literal["rep_visit", "rep_invite", "supplier_import", "referral"] | None = None
    next_follow_up_at: datetime | None = None


class CustomerUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = None
    email: EmailStr | None = None
    city_id: int | None = None
    district: str | None = Field(default=None, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    status: CustomerStatus | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    next_follow_up_at: datetime | None = None
    assigned_representative_id: uuid.UUID | None = None


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    role: str | None = Field(default=None, max_length=80)
    phone: str | None = None
    email: EmailStr | None = None


class OpportunityIn(BaseModel):
    customer_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    estimated_value: Decimal | None = Field(default=None, ge=0)
    stage: OpportunityStage = OpportunityStage.open
    expected_close_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=4000)
    supplier_id: uuid.UUID | None = None


# ------------------------------------------------------------------ generic implementation
def _list(db: Session, owner: Owner, locale: str, params: PageParams, q, status, city_id, assigned_rep_id, tag, due_follow_up):
    stmt = select(Customer).where(owner.filter()).order_by(Customer.updated_at.desc())
    if q:
        stmt = stmt.where(or_(Customer.name.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%"), Customer.contact_name.ilike(f"%{q}%")))
    if status:
        stmt = stmt.where(Customer.status == status)
    if city_id:
        stmt = stmt.where(Customer.city_id == city_id)
    if assigned_rep_id:
        stmt = stmt.where(Customer.assigned_representative_id == assigned_rep_id)
    if tag:
        stmt = stmt.where(Customer.tags.contains([tag]))
    if due_follow_up:
        stmt = stmt.where(Customer.next_follow_up_at <= utcnow() + timedelta(days=1))
    return paginate(db, stmt, params, lambda c: customer_out(db, c, locale))


def _get(db: Session, owner: Owner, cid: uuid.UUID) -> Customer:
    c = db.get(Customer, cid)
    if c is None or (owner.supplier_id and c.owner_supplier_id != owner.supplier_id) or \
            (owner.rep_id and c.owner_representative_id != owner.rep_id):
        raise NotFound()
    return c


def _create(db: Session, owner: Owner, data: CustomerIn, user_id, default_source: AcquisitionSource) -> Customer:
    phone = normalize_phone(data.phone) if data.phone else None
    if data.phone and not phone:
        raise ValidationFailed("invalid_phone", fields={"phone": "invalid"})
    if data.city_id and db.get(City, data.city_id) is None:
        raise ValidationFailed("invalid_city")
    retailer = None
    if data.retailer_id:
        retailer = db.get(Business, data.retailer_id)
        if retailer is None or retailer.type != BusinessType.retailer:
            raise ValidationFailed("invalid_retailer")
        if db.scalar(select(Customer.id).where(owner.filter(), Customer.retailer_id == retailer.id)):
            raise Conflict("customer_exists")
    elif not data.name:
        raise ValidationFailed("name_required", fields={"name": "required"})
    branch = next((b for b in retailer.branches if b.is_primary), None) if retailer else None
    c = Customer(**owner.kwargs(), retailer_id=retailer.id if retailer else None, branch_id=branch.id if branch else None,
                 name=data.name or retailer.trade_name_ar, contact_name=data.contact_name, phone=phone,
                 email=data.email, city_id=data.city_id or (branch.city_id if branch else None),
                 district=data.district or (branch.district if branch else None), address_line=data.address_line,
                 lat=data.lat if data.lat is not None else (branch.lat if branch else None),
                 lng=data.lng if data.lng is not None else (branch.lng if branch else None),
                 status=CustomerStatus.prospect if retailer else CustomerStatus.lead,
                 source=AcquisitionSource(data.source) if data.source else default_source, tags=data.tags,
                 next_follow_up_at=data.next_follow_up_at, created_by=user_id)
    db.add(c)
    db.flush()
    return c


def _update(db: Session, c: Customer, data: CustomerUpdateIn, supplier_id=None) -> dict:
    values = data.model_dump(exclude_unset=True)
    if "phone" in values and values["phone"]:
        values["phone"] = normalize_phone(values["phone"])
        if not values["phone"]:
            raise ValidationFailed("invalid_phone")
    if values.get("city_id") and db.get(City, values["city_id"]) is None:
        raise ValidationFailed("invalid_city")
    if "assigned_representative_id" in values:
        rid = values["assigned_representative_id"]
        if supplier_id is None:
            raise ValidationFailed("not_allowed", fields={"assigned_representative_id": "supplier_only"})
        if rid:
            linked = db.scalar(select(RepresentativeCompany.id).where(RepresentativeCompany.supplier_id == supplier_id,
                                                                      RepresentativeCompany.representative_id == rid,
                                                                      RepresentativeCompany.status == RepCompanyStatus.active))
            if not linked:
                raise ValidationFailed("representative_not_linked")
            for prev in db.scalars(select(CustomerAssignment).where(CustomerAssignment.customer_id == c.id,
                                                                    CustomerAssignment.ends_at.is_(None))):
                prev.ends_at = utcnow()
            db.add(CustomerAssignment(customer_id=c.id, representative_id=rid))
    for k, v in values.items():
        setattr(c, k, v)
    return values


# ------------------------------------------------------------------ supplier routes
@router.get("/supplier/customers")
def s_list(q: str | None = None, status: CustomerStatus | None = None, city_id: int | None = None,
           assigned_rep_id: uuid.UUID | None = None, tag: str | None = None, due_follow_up: bool = False,
           params: PageParams = Depends(), db: Session = Depends(get_db),
           ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.view"))):
    return _list(db, Owner(supplier_id=ctx.business_id), ctx.principal.locale, params, q, status, city_id, assigned_rep_id,
                 tag, due_follow_up)


@router.post("/supplier/customers", status_code=201)
def s_create(data: CustomerIn, request: Request, db: Session = Depends(get_db),
             ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.manage"))):
    c = _create(db, Owner(supplier_id=ctx.business_id), data, ctx.user.id, AcquisitionSource.supplier_import)
    audit(db, "customer.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="customer",
          entity_id=c.id, request=request)
    db.commit()
    return customer_out(db, c, ctx.principal.locale)


@router.get("/supplier/customers/{cid}")
def s_get(cid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.view"))):
    return customer_out(db, _get(db, Owner(supplier_id=ctx.business_id), cid), ctx.principal.locale, detail=True)


@router.patch("/supplier/customers/{cid}")
def s_update(cid: uuid.UUID, data: CustomerUpdateIn, request: Request, db: Session = Depends(get_db),
             ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.manage"))):
    c = _get(db, Owner(supplier_id=ctx.business_id), cid)
    changes = _update(db, c, data, supplier_id=ctx.business_id)
    audit(db, "customer.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="customer",
          entity_id=c.id, changes=changes, request=request)
    db.commit()
    return customer_out(db, c, ctx.principal.locale)


@router.post("/supplier/customers/{cid}/notes", status_code=201)
def s_note(cid: uuid.UUID, data: NoteIn, db: Session = Depends(get_db),
           ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.manage"))):
    c = _get(db, Owner(supplier_id=ctx.business_id), cid)
    db.add(CustomerNote(customer_id=c.id, author_user_id=ctx.user.id, body=data.body))
    db.commit()
    return {"ok": True}


@router.post("/supplier/customers/{cid}/contacts", status_code=201)
def s_contact(cid: uuid.UUID, data: ContactIn, db: Session = Depends(get_db),
              ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.manage"))):
    c = _get(db, Owner(supplier_id=ctx.business_id), cid)
    db.add(CustomerContact(customer_id=c.id, name=data.name, role=data.role,
                           phone=normalize_phone(data.phone) if data.phone else None, email=data.email))
    db.commit()
    return {"ok": True}


class SourceChangeIn(BaseModel):
    source: AcquisitionSource
    representative_id: uuid.UUID | None = None
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/supplier/customers/{cid}/source")
def s_change_source(cid: uuid.UUID, data: SourceChangeIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.source_change"))):
    """Changing the recorded acquisition source requires a dedicated permission and a documented reason."""
    c = _get(db, Owner(supplier_id=ctx.business_id), cid)
    if not c.retailer_id:
        raise ValidationFailed("customer_not_registered")
    acq = db.scalar(select(CustomerAcquisition).where(CustomerAcquisition.supplier_id == ctx.business_id,
                                                      CustomerAcquisition.retailer_id == c.retailer_id))
    if acq is None:
        raise NotFound("acquisition_not_found")
    if data.representative_id:
        linked = db.scalar(select(RepresentativeCompany.id).where(RepresentativeCompany.supplier_id == ctx.business_id,
                                                                  RepresentativeCompany.representative_id == data.representative_id))
        if not linked:
            raise ValidationFailed("representative_not_linked")
    db.add(CustomerSourceChange(acquisition_id=acq.id, old_source=acq.source.value, new_source=data.source.value,
                                old_representative_id=acq.representative_id, new_representative_id=data.representative_id,
                                reason=data.reason, changed_by=ctx.user.id))
    old = {"source": acq.source.value, "representative_id": acq.representative_id}
    acq.source = data.source
    acq.representative_id = data.representative_id
    audit(db, "customer.source_change", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          entity_type="customer_acquisition", entity_id=acq.id, reason=data.reason,
          changes={"old": old, "new": data.model_dump()}, request=request)
    db.commit()
    return customer_out(db, c, ctx.principal.locale, detail=True)


@router.get("/supplier/opportunities")
def s_opps(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.view"))):
    rows = db.scalars(select(Opportunity).where(Opportunity.owner_supplier_id == ctx.business_id)
                      .order_by(Opportunity.created_at.desc()).limit(500)).all()
    return [opp_out(o) for o in rows]


@router.post("/supplier/opportunities", status_code=201)
def s_opp_create(data: OpportunityIn, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.customers.manage"))):
    _get(db, Owner(supplier_id=ctx.business_id), data.customer_id)
    o = Opportunity(owner_supplier_id=ctx.business_id, supplier_id=ctx.business_id,
                    **data.model_dump(exclude={"supplier_id"}))
    db.add(o)
    db.commit()
    return opp_out(o)


# ------------------------------------------------------------------ representative routes
@router.get("/rep/customers")
def r_list(q: str | None = None, status: CustomerStatus | None = None, city_id: int | None = None, tag: str | None = None,
           due_follow_up: bool = False, params: PageParams = Depends(), db: Session = Depends(get_db),
           ctx: RepCtx = Depends(rep_ctx())):
    return _list(db, Owner(rep_id=ctx.rep.id), ctx.principal.locale, params, q, status, city_id, None, tag, due_follow_up)


@router.post("/rep/customers", status_code=201)
def r_create(data: CustomerIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    c = _create(db, Owner(rep_id=ctx.rep.id), data, ctx.user.id, AcquisitionSource.rep_visit)
    audit(db, "customer.create", actor_user_id=ctx.user.id, entity_type="customer", entity_id=c.id, request=request)
    db.commit()
    return customer_out(db, c, ctx.principal.locale)


@router.get("/rep/customers/{cid}")
def r_get(cid: uuid.UUID, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return customer_out(db, _get(db, Owner(rep_id=ctx.rep.id), cid), ctx.principal.locale, detail=True)


@router.patch("/rep/customers/{cid}")
def r_update(cid: uuid.UUID, data: CustomerUpdateIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    c = _get(db, Owner(rep_id=ctx.rep.id), cid)
    _update(db, c, data)
    db.commit()
    return customer_out(db, c, ctx.principal.locale)


@router.post("/rep/customers/{cid}/notes", status_code=201)
def r_note(cid: uuid.UUID, data: NoteIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    c = _get(db, Owner(rep_id=ctx.rep.id), cid)
    db.add(CustomerNote(customer_id=c.id, author_user_id=ctx.user.id, body=data.body))
    db.commit()
    return {"ok": True}


@router.post("/rep/customers/{cid}/contacts", status_code=201)
def r_contact(cid: uuid.UUID, data: ContactIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    c = _get(db, Owner(rep_id=ctx.rep.id), cid)
    db.add(CustomerContact(customer_id=c.id, name=data.name, role=data.role,
                           phone=normalize_phone(data.phone) if data.phone else None, email=data.email))
    db.commit()
    return {"ok": True}


@router.get("/rep/opportunities")
def r_opps(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    rows = db.scalars(select(Opportunity).where(Opportunity.owner_representative_id == ctx.rep.id)
                      .order_by(Opportunity.created_at.desc()).limit(500)).all()
    return [opp_out(o) for o in rows]


@router.post("/rep/opportunities", status_code=201)
def r_opp_create(data: OpportunityIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    _get(db, Owner(rep_id=ctx.rep.id), data.customer_id)
    o = Opportunity(owner_representative_id=ctx.rep.id, **data.model_dump())
    db.add(o)
    db.commit()
    return opp_out(o)


class OppUpdateIn(BaseModel):
    stage: OpportunityStage | None = None
    estimated_value: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=4000)
    expected_close_at: datetime | None = None


@router.patch("/rep/opportunities/{oid}")
def r_opp_update(oid: uuid.UUID, data: OppUpdateIn, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    o = db.get(Opportunity, oid)
    if o is None or o.owner_representative_id != ctx.rep.id:
        raise NotFound()
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    db.commit()
    return opp_out(o)


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


@router.get("/rep/discover")
def discover_stores(lat: float | None = None, lng: float | None = None, radius_km: float = 10, city_id: int | None = None,
                    q: str | None = None, limit: int = 50, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    """Registered stores that opted into discovery, within the rep's work areas (or near a given point).
    Location is used only for this request and not stored."""
    limit = max(1, min(limit, 200))
    radius_km = max(0.5, min(radius_km, 100))
    my_cities = [a.city_id for a in db.scalars(select(RepresentativeArea).where(RepresentativeArea.representative_id == ctx.rep.id))]
    stmt = (select(Branch, Business).join(Business, Business.id == Branch.business_id)
            .where(Business.type == BusinessType.retailer, Business.discoverable.is_(True),
                   Business.status == BusinessStatus.active, Branch.is_active.is_(True)))
    if city_id:
        stmt = stmt.where(Branch.city_id == city_id)
    elif lat is None and my_cities:
        stmt = stmt.where(Branch.city_id.in_(my_cities))
    if q:
        stmt = stmt.where(or_(Business.trade_name_ar.ilike(f"%{q}%"), Business.trade_name_en.ilike(f"%{q}%"),
                              Branch.district.ilike(f"%{q}%")))
    if lat is not None and lng is not None:
        dlat = radius_km / 111.0
        dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.1))
        stmt = stmt.where(Branch.lat.between(lat - dlat, lat + dlat), Branch.lng.between(lng - dlng, lng + dlng))
    rows = db.execute(stmt.limit(limit * 3)).all()
    in_crm = set(db.scalars(select(Customer.retailer_id).where(Customer.owner_representative_id == ctx.rep.id,
                                                               Customer.retailer_id.isnot(None))))
    out = []
    for br, biz in rows:
        dist = _haversine_km(lat, lng, br.lat, br.lng) if (lat is not None and br.lat is not None) else None
        if dist is not None and dist > radius_km:
            continue
        out.append({"retailer_id": str(biz.id), "branch_id": str(br.id), "name": biz.trade_name_ar,
                    "name_en": biz.trade_name_en, "branch_name": br.name, "store_type": biz.store_type,
                    "city": city_out(br.city, ctx.principal.locale), "district": br.district, "lat": br.lat, "lng": br.lng,
                    "distance_km": round(dist, 2) if dist is not None else None, "in_my_crm": biz.id in in_crm,
                    "verification_status": biz.verification_status.value})
    out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0, x["name"]))
    return out[:limit]


@router.get("/rep/sales-opportunities")
def sales_opportunities(db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    """Actionable opportunities: lapsed customers, due follow-ups, open opportunities, undiscovered stores."""
    now = utcnow()
    lapsed = db.scalars(select(Customer).where(Customer.owner_representative_id == ctx.rep.id,
                                               Customer.status == CustomerStatus.active,
                                               Customer.last_order_at < now - timedelta(days=21)).limit(20)).all()
    due = db.scalars(select(Customer).where(Customer.owner_representative_id == ctx.rep.id,
                                            Customer.next_follow_up_at <= now + timedelta(days=1)).limit(20)).all()
    opps = db.scalars(select(Opportunity).where(Opportunity.owner_representative_id == ctx.rep.id,
                                                Opportunity.stage.in_([OpportunityStage.open, OpportunityStage.negotiation]))
                      .limit(20)).all()
    with system_context(db):
        pending = db.scalar(select(func.count()).select_from(Order).where(
            Order.representative_id == ctx.rep.id, Order.status == OrderStatus.pending_retailer_approval)) or 0
    loc = ctx.principal.locale
    return {"lapsed_customers": [customer_out(db, c, loc) for c in lapsed],
            "due_follow_ups": [customer_out(db, c, loc) for c in due],
            "open_opportunities": [opp_out(o) for o in opps], "orders_awaiting_store_approval": pending}
