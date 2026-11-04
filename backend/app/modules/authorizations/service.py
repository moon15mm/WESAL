"""Authorization rules: a representative may act for a supplier only through an
ACTIVE authorization whose date window, product scope and area scope cover the action."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, InvalidTransition
from app.core.utils import utcnow
from app.models.catalog import Product
from app.models.enums import AuthorizationStatus as S
from app.models.enums import AuthorizationType
from app.models.reps import Authorization, AuthorizationHistory

TRANSITIONS: dict[S, set[S]] = {
    S.draft: {S.pending_rep, S.cancelled},
    S.sent: {S.pending_rep, S.cancelled},
    S.pending_rep: {S.active, S.cancelled, S.pending_rep},
    S.active: {S.suspended, S.expired, S.cancelled, S.pending_rep},
    S.suspended: {S.active, S.cancelled, S.expired},
    S.expired: set(),
    S.cancelled: set(),
}


def snapshot(a: Authorization) -> dict:
    return {
        "type": a.type.value, "all_products": a.all_products, "all_areas": a.all_areas,
        "start_date": a.start_date.isoformat() if a.start_date else None,
        "end_date": a.end_date.isoformat() if a.end_date else None, "terms": a.terms,
        "agreement_id": str(a.agreement_id) if a.agreement_id else None,
        "products": sorted([f"p:{x.product_id}" if x.product_id else f"c:{x.category_id}" if x.category_id else f"b:{x.brand_id}"
                            for x in a.products]),
        "areas": sorted([f"{x.city_id}:{x.district or ''}" for x in a.areas]),
        "agreement_rules": [{"basis": r.basis.value, "rate": str(r.rate), "scope": r.scope.value,
                             "product_id": str(r.product_id) if r.product_id else None, "category_id": r.category_id}
                            for r in (a.agreement.rules if a.agreement else [])],
    }


def terms_hash(a: Authorization) -> str:
    return hashlib.sha256(json.dumps(snapshot(a), sort_keys=True).encode()).hexdigest()


def transition(db: Session, a: Authorization, to: S, actor_user_id: uuid.UUID | None, action: str, reason: str | None = None) -> None:
    if to not in TRANSITIONS[a.status]:
        raise InvalidTransition("authorization_invalid_transition", params={"from": a.status.value, "to": to.value})
    prev = a.status
    a.status = to
    a.status_reason = reason
    db.add(AuthorizationHistory(authorization_id=a.id, action=action, from_status=prev.value, to_status=to.value,
                                actor_user_id=actor_user_id, reason=reason, snapshot=snapshot(a)))


def is_effective(a: Authorization, on: date | None = None) -> bool:
    on = on or utcnow().date()
    if a.status != S.active:
        return False
    if a.start_date and on < a.start_date:
        return False
    if a.end_date and on > a.end_date:
        return False
    return True


def covers_product(a: Authorization, product: Product) -> bool:
    if a.all_products:
        return True
    for scope in a.products:
        if scope.product_id and scope.product_id == product.id:
            return True
        if scope.category_id and scope.category_id == product.category_id:
            return True
        if scope.brand_id and scope.brand_id == product.brand_id:
            return True
    return False


def covers_area(a: Authorization, city_id: int | None, district: str | None = None) -> bool:
    if a.all_areas:
        return True
    if city_id is None:
        return False
    for area in a.areas:
        if area.city_id == city_id and (not area.district or (district and area.district.strip().lower() == district.strip().lower())):
            return True
    return False


def require_order_authorization(db: Session, rep_id: uuid.UUID, supplier_id: uuid.UUID, products: list[Product],
                                city_id: int | None, district: str | None = None) -> Authorization:
    """Return the authorization permitting `rep` to sell `products` of `supplier` in `city`, or raise."""
    candidates = db.scalars(select(Authorization).where(Authorization.representative_id == rep_id,
                                                        Authorization.supplier_id == supplier_id,
                                                        Authorization.status == S.active)).all()
    reasons = "authorization_missing"
    for a in candidates:
        if not is_effective(a):
            reasons = "authorization_not_effective"
            continue
        if a.type == AuthorizationType.promotion_only:
            reasons = "authorization_no_order_rights"
            continue
        if not covers_area(a, city_id, district):
            reasons = "authorization_area_not_covered"
            continue
        if not all(covers_product(a, p) for p in products):
            reasons = "authorization_product_not_covered"
            continue
        return a
    raise Forbidden(reasons)


def authorized_scope_filter(a: Authorization):
    """SQL filter on Product for the products an authorization covers."""
    from sqlalchemy import false, or_

    if a.all_products:
        return None
    conds = []
    pids = [s.product_id for s in a.products if s.product_id]
    cids = [s.category_id for s in a.products if s.category_id]
    bids = [s.brand_id for s in a.products if s.brand_id]
    if pids:
        conds.append(Product.id.in_(pids))
    if cids:
        conds.append(Product.category_id.in_(cids))
    if bids:
        conds.append(Product.brand_id.in_(bids))
    return or_(*conds) if conds else false()
