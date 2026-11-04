"""Shared helpers: business context for either business type, serializers."""
from __future__ import annotations

import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import BusinessCtx, Principal, _business_ctx, current_principal
from app.core.errors import Forbidden
from app.core.i18n import localized
from app.models.business import Business, City
from app.models.enums import BusinessType


def any_business_ctx(perm_suffix: str | None = None):
    """Resolve a business context of any type; permission is `<type>.<perm_suffix>`."""

    def dep(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)) -> BusinessCtx:
        selector = request.headers.get("x-business-id")
        btype: BusinessType | None = None
        if selector:
            m = next((m for m in principal.memberships if str(m.business_id) == selector), None)
            if m:
                btype = m.business.type
        elif len(principal.memberships) == 1:
            btype = principal.memberships[0].business.type
        if btype is None:
            if not principal.memberships:
                raise Forbidden("no_business_context", params={"type": "any"})
            if not selector:
                raise Forbidden("business_context_required")
            btype = BusinessType.retailer  # will fail membership check and be audited
        perm = f"{btype.value}.{perm_suffix}" if perm_suffix else None
        return _business_ctx(request, db, principal, btype, perm)

    return dep


def file_url(file_id: uuid.UUID | None) -> str | None:
    return f"/api/v1/files/{file_id}" if file_id else None


def city_out(city: City | None, locale: str) -> dict | None:
    if city is None:
        return None
    return {"id": city.id, "code": city.code, "name": localized(city.name, locale), "region_id": city.region_id}


def business_brief(b: Business | None, locale: str) -> dict | None:
    if b is None:
        return None
    return {
        "id": str(b.id), "type": b.type.value, "name": b.display_name(locale), "trade_name_ar": b.trade_name_ar,
        "trade_name_en": b.trade_name_en, "slug": b.slug, "logo_url": file_url(b.logo_file_id),
        "verification_status": b.verification_status.value, "rating_avg": round(b.rating_avg or 0, 2),
        "rating_count": b.rating_count, "city": city_out(b.city, locale),
    }


def product_name(p, locale: str) -> str:
    if locale == "ar":
        return p.name_ar
    if locale in ("ur", "hi") and (p.name_i18n or {}).get(locale):
        return p.name_i18n[locale]
    return p.name_en or p.name_ar
