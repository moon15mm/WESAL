"""Public, unauthenticated endpoints: reference data, content pages, contact form."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.db import get_db, system_context
from app.core.deps import request_locale
from app.core.errors import NotFound
from app.core.i18n import localized
from app.models.business import Business, City, Region
from app.models.catalog import Category, SupplierProduct
from app.models.enums import BusinessStatus, BusinessType, VerificationStatus
from app.models.reps import Representative
from app.models.system import ContactMessage, ContentPage, Language, PlatformSetting, SubscriptionPlan, TranslationOverride

router = APIRouter(prefix="/ref", tags=["reference"])
public = APIRouter(prefix="/public", tags=["public"])


@router.get("/regions")
def regions(request: Request, db: Session = Depends(get_db)):
    loc = request_locale(request)
    return [{"id": r.id, "code": r.code, "name": localized(r.name, loc)} for r in db.scalars(select(Region).order_by(Region.id))]


@router.get("/cities")
def cities(request: Request, region_id: int | None = None, db: Session = Depends(get_db)):
    loc = request_locale(request)
    stmt = select(City).order_by(City.id)
    if region_id:
        stmt = stmt.where(City.region_id == region_id)
    return [{"id": c.id, "code": c.code, "name": localized(c.name, loc), "region_id": c.region_id, "lat": c.lat, "lng": c.lng}
            for c in db.scalars(stmt)]


@router.get("/categories")
def categories(request: Request, db: Session = Depends(get_db)):
    loc = request_locale(request)
    rows = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order)).all()
    return [{"id": c.id, "slug": c.slug, "name": localized(c.name, loc), "names": c.name, "icon": c.icon,
             "parent_id": c.parent_id} for c in rows]


@router.get("/languages")
def languages(db: Session = Depends(get_db)):
    rows = db.scalars(select(Language).where(Language.is_enabled.is_(True)).order_by(Language.sort_order)).all()
    return [{"code": l.code, "name": l.name, "native_name": l.native_name, "direction": l.direction} for l in rows]


@router.get("/settings")
def public_settings(db: Session = Depends(get_db)):
    return {s.key: s.value for s in db.scalars(select(PlatformSetting).where(PlatformSetting.is_public.is_(True)))}


@router.get("/plans")
def plans(request: Request, db: Session = Depends(get_db)):
    loc = request_locale(request)
    rows = db.scalars(select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(
        SubscriptionPlan.audience, SubscriptionPlan.sort_order)).all()
    return [{"code": p.code, "audience": p.audience, "name": localized(p.name, loc), "price_monthly": p.price_monthly,
             "price_yearly": p.price_yearly, "limits": p.limits, "features": p.features} for p in rows]


@router.get("/translations/{locale}")
def translation_overrides(locale: Literal["ar", "en", "ur", "hi"], db: Session = Depends(get_db)):
    """Runtime translation overrides edited by admins; merged over the frontend bundles."""
    rows = db.scalars(select(TranslationOverride).where(TranslationOverride.locale == locale)).all()
    return {r.key: r.value for r in rows}


@public.get("/pages/{slug}")
def page(slug: str, request: Request, db: Session = Depends(get_db)):
    loc = request_locale(request)
    row = db.scalar(select(ContentPage).where(ContentPage.slug == slug, ContentPage.locale == loc, ContentPage.is_published.is_(True)))
    if row is None:
        row = db.scalar(select(ContentPage).where(ContentPage.slug == slug, ContentPage.locale.in_(["en", "ar"]),
                                                  ContentPage.is_published.is_(True)).order_by(ContentPage.locale.desc()))
    if row is None:
        raise NotFound()
    return {"slug": row.slug, "locale": row.locale, "title": row.title, "body": row.body, "version": row.version,
            "updated_at": row.updated_at}


@public.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Aggregate, non-sensitive marketplace numbers for the landing page."""
    with system_context(db):
        suppliers = db.scalar(select(func.count()).select_from(Business).where(
            Business.type == BusinessType.supplier, Business.verification_status == VerificationStatus.verified,
            Business.status == BusinessStatus.active))
        stores = db.scalar(select(func.count()).select_from(Business).where(Business.type == BusinessType.retailer))
        reps = db.scalar(select(func.count()).select_from(Representative).where(
            Representative.verification_status == VerificationStatus.verified))
        products = db.scalar(select(func.count()).select_from(SupplierProduct).where(SupplierProduct.is_active.is_(True)))
        cities_n = db.scalar(select(func.count()).select_from(City))
    return {"suppliers": suppliers or 0, "stores": stores or 0, "representatives": reps or 0, "offers": products or 0,
            "cities": cities_n or 0}


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    audience: Literal["retailer", "supplier", "representative", "other"] | None = None
    message: str = Field(min_length=10, max_length=4000)
    website: str | None = None  # honeypot


@public.post("/contact", status_code=201)
def contact(data: ContactIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.hit(f"contact:{request.state.client_ip}", 5, 3600)
    if data.website:  # bots fill hidden fields
        return {"ok": True}
    db.add(ContactMessage(name=data.name, email=data.email, phone=data.phone, audience=data.audience, message=data.message))
    db.commit()
    return {"ok": True}
