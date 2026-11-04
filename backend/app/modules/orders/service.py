"""Order engine: line building & pricing, totals, state machine, approvals snapshots."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import system_context
from app.core.errors import InvalidTransition, ValidationFailed
from app.core.utils import money, utcnow
from app.models.business import Branch, Business, CoverageArea
from app.models.catalog import SupplierProduct
from app.models.enums import (
    ApprovalDecision,
    Availability,
    BusinessStatus,
    BusinessType,
    OrderStatus as S,
    SaleUnit,
    VerificationStatus,
)
from app.models.orders import Order, OrderApproval, OrderItem, OrderStatusHistory
from app.modules.catalog.pricing import PricingContext

TRANSITIONS: dict[S, set[S]] = {
    S.draft: {S.pending_retailer_approval, S.new, S.cancelled},
    S.pending_retailer_approval: {S.new, S.rejected, S.draft, S.cancelled},
    S.new: {S.supplier_review, S.approved, S.quoted, S.rejected, S.cancelled},
    S.supplier_review: {S.quoted, S.approved, S.rejected, S.cancelled},
    S.quoted: {S.approved, S.rejected, S.supplier_review, S.cancelled},
    S.awaiting_retailer_approval: {S.approved, S.cancelled},
    S.approved: {S.preparing, S.awaiting_retailer_approval, S.cancelled},
    S.preparing: {S.ready, S.awaiting_retailer_approval, S.cancelled},
    S.ready: {S.out_for_delivery, S.cancelled},
    S.out_for_delivery: {S.delivered, S.ready},
    S.delivered: {S.completed, S.disputed, S.partially_returned, S.fully_returned},
    S.completed: {S.partially_returned, S.fully_returned, S.disputed},
    S.partially_returned: {S.partially_returned, S.fully_returned, S.disputed, S.completed},
    S.disputed: {S.completed, S.delivered, S.partially_returned, S.fully_returned, S.cancelled},
    S.fully_returned: set(),
    S.rejected: set(),
    S.cancelled: set(),
}

TERMINAL = {S.rejected, S.cancelled, S.fully_returned}
ACTIVE_FOR_SUPPLIER = {S.new, S.supplier_review, S.quoted, S.awaiting_retailer_approval, S.approved, S.preparing,
                       S.ready, S.out_for_delivery, S.delivered, S.completed, S.partially_returned, S.fully_returned,
                       S.disputed, S.rejected, S.cancelled}
SALES_STATUSES = {S.approved, S.preparing, S.ready, S.out_for_delivery, S.delivered, S.completed, S.partially_returned,
                  S.disputed}


def transition(db: Session, order: Order, to: S, actor_user_id, actor_role: str, reason: str | None = None) -> None:
    if to not in TRANSITIONS[order.status]:
        raise InvalidTransition("order_invalid_transition", params={"from": order.status.value, "to": to.value})
    prev = order.status
    order.status = to
    order.status_reason = reason
    now = utcnow()
    if to == S.approved:
        order.approved_at = now
        order.approved_version = order.version
    elif to == S.delivered:
        order.delivered_at = now
    elif to == S.completed:
        order.completed_at = order.completed_at or now
    elif to in (S.cancelled, S.rejected):
        order.cancelled_at = now
    elif to in (S.new, S.pending_retailer_approval) and order.submitted_at is None:
        order.submitted_at = now
    db.add(OrderStatusHistory(order_id=order.id, from_status=prev.value, to_status=to.value, actor_user_id=actor_user_id,
                              actor_role=actor_role, reason=reason, version=order.version))


@dataclass
class LineIn:
    offer_id: uuid.UUID
    unit: SaleUnit
    quantity: int
    unit_price: Decimal | None = None  # supplier offers only
    discount: Decimal | None = None  # supplier offers only (line total)


def supplier_for_orders(db: Session, supplier_id: uuid.UUID) -> Business:
    with system_context(db):
        sup = db.get(Business, supplier_id)
    if sup is None or sup.type != BusinessType.supplier or sup.status != BusinessStatus.active or \
            sup.verification_status != VerificationStatus.verified:
        raise ValidationFailed("invalid_supplier")
    return sup


def coverage_for(db: Session, supplier_id: uuid.UUID, city_id: int | None, district: str | None) -> CoverageArea | None:
    areas = db.scalars(select(CoverageArea).where(CoverageArea.supplier_id == supplier_id, CoverageArea.is_active.is_(True))).all()
    if not areas:
        return None
    match = [a for a in areas if a.city_id == city_id and (not a.district or (district and a.district.strip().lower() == district.strip().lower()))]
    if not match:
        raise ValidationFailed("supplier_not_covering_area")
    return sorted(match, key=lambda a: a.district is None)[0]


def build_items(db: Session, order: Order, lines: list[LineIn], *, pricing: PricingContext, allow_price_override: bool = False) -> None:
    if not lines:
        raise ValidationFailed("order_empty")
    if len(lines) > 300:
        raise ValidationFailed("too_many_items")
    keys = [(l.offer_id, l.unit) for l in lines]
    if len(set(keys)) != len(keys):
        raise ValidationFailed("duplicate_items")
    offers = {sp.id: sp for sp in db.scalars(select(SupplierProduct).where(SupplierProduct.id.in_([l.offer_id for l in lines])))}
    # keep existing line identities (ids are referenced by offers, confirmations and returns)
    existing = {(i.supplier_product_id, i.unit): i for i in order.items}
    wanted = {(l.offer_id, l.unit) for l in lines}
    for key, item in list(existing.items()):
        if key not in wanted:
            order.items.remove(item)
    db.flush()
    for pos, line in enumerate(lines):
        sp = offers.get(line.offer_id)
        if sp is None or sp.supplier_id != order.supplier_id or not sp.is_active:
            raise ValidationFailed("invalid_offer", params={"offer_id": str(line.offer_id)})
        if sp.availability in (Availability.out_of_stock, Availability.discontinued):
            raise ValidationFailed("offer_unavailable", params={"product": sp.product.name_ar})
        if line.unit == SaleUnit.piece and not sp.sell_by_piece or line.unit == SaleUnit.carton and not sp.sell_by_carton:
            raise ValidationFailed("unit_not_allowed", params={"product": sp.product.name_ar})
        if line.quantity <= 0 or line.quantity > 100000:
            raise ValidationFailed("invalid_quantity")
        price = pricing.price(sp, line.unit, line.quantity)
        pieces = line.quantity * price.pieces_per_unit
        if pieces < sp.min_order_qty:
            raise ValidationFailed("below_min_order_qty", params={"product": sp.product.name_ar, "min": sp.min_order_qty})
        if sp.stock_qty is not None and pieces > sp.stock_qty:
            raise ValidationFailed("insufficient_stock", params={"product": sp.product.name_ar, "available": sp.stock_qty})
        unit_price = price.list_unit_price
        discount = money(price.discount_per_unit * line.quantity)
        if allow_price_override:
            if line.unit_price is not None:
                unit_price = money(line.unit_price)
            if line.discount is not None:
                discount = money(line.discount)
        gross = money(unit_price * line.quantity)
        if discount < 0 or discount > gross:
            raise ValidationFailed("invalid_discount")
        values = dict(
            position=pos, supplier_product_id=sp.id, product_id=sp.product_id, name_ar=sp.product.name_ar,
            name_en=sp.product.name_en, sku=sp.sku, unit=line.unit, pieces_per_unit=price.pieces_per_unit,
            quantity=line.quantity, list_unit_price=price.list_unit_price, unit_price=unit_price, discount=discount,
            promotion_id=price.promotion_id, line_total=money(gross - discount), category_id=sp.product.category_id,
            brand_id=sp.product.brand_id,
        )
        item = existing.get((sp.id, line.unit))
        if item is not None:
            for k, v in values.items():
                setattr(item, k, v)
        else:
            order.items.append(OrderItem(**values))
    order.items.sort(key=lambda i: i.position)


def recompute_totals(order: Order, supplier: Business, delivery_fee: Decimal | None = None) -> None:
    subtotal = sum((money(i.unit_price * i.quantity) for i in order.items), Decimal("0"))
    discount = sum((money(i.discount) for i in order.items), Decimal("0"))
    if delivery_fee is not None:
        order.delivery_fee = money(delivery_fee)
    rate = Decimal(str(settings.vat_rate)) if supplier.vat_registered else Decimal("0")
    taxable = subtotal - discount + Decimal(order.delivery_fee or 0)
    for i in order.items:
        i.vat_amount = money(i.line_total * rate)
    order.subtotal = money(subtotal)
    order.discount_total = money(discount)
    order.vat_rate = rate
    order.vat_total = money(taxable * rate)
    order.total = money(taxable + order.vat_total)


def check_minimums(order: Order, supplier: Business, cov: CoverageArea | None) -> None:
    minimum = (cov.min_order_value if cov and cov.min_order_value is not None else supplier.min_order_value) or Decimal("0")
    net = order.subtotal - order.discount_total
    if net < minimum:
        raise ValidationFailed("below_min_order_value", params={"min": str(minimum)})


def snapshot(order: Order) -> dict:
    return {
        "version": order.version, "supplier_id": str(order.supplier_id), "retailer_id": str(order.retailer_id),
        "branch_id": str(order.branch_id) if order.branch_id else None,
        "items": [{"offer_id": str(i.supplier_product_id), "product_id": str(i.product_id), "name_ar": i.name_ar,
                   "name_en": i.name_en, "unit": i.unit.value, "quantity": i.quantity, "unit_price": str(i.unit_price),
                   "discount": str(i.discount), "line_total": str(i.line_total)} for i in order.items],
        "subtotal": str(order.subtotal), "discount_total": str(order.discount_total), "delivery_fee": str(order.delivery_fee),
        "vat_total": str(order.vat_total), "total": str(order.total),
    }


def snapshot_hash(snap: dict) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def open_approval(db: Session, order: Order, kind: str, requested_by) -> OrderApproval:
    """Supersede pending approvals and request the retailer's approval of the current version."""
    for prev in db.scalars(select(OrderApproval).where(OrderApproval.order_id == order.id,
                                                       OrderApproval.decision == ApprovalDecision.pending)):
        prev.decision = ApprovalDecision.superseded
        prev.decided_at = utcnow()
    db.flush()
    snap = snapshot(order)
    ap = OrderApproval(order_id=order.id, version=order.version, kind=kind, requested_by=requested_by, snapshot=snap,
                       snapshot_hash=snapshot_hash(snap))
    db.add(ap)
    db.flush()
    return ap


def pending_approval(db: Session, order: Order) -> OrderApproval | None:
    return db.scalar(select(OrderApproval).where(OrderApproval.order_id == order.id,
                                                 OrderApproval.decision == ApprovalDecision.pending)
                     .order_by(OrderApproval.requested_at.desc()).limit(1))


def branch_for(db: Session, retailer_id: uuid.UUID, branch_id: uuid.UUID | None) -> Branch:
    if branch_id:
        br = db.get(Branch, branch_id)
        if br is None or br.business_id != retailer_id or not br.is_active:
            raise ValidationFailed("invalid_branch")
        return br
    br = db.scalar(select(Branch).where(Branch.business_id == retailer_id, Branch.is_primary.is_(True)))
    if br is None:
        br = db.scalar(select(Branch).where(Branch.business_id == retailer_id, Branch.is_active.is_(True)))
    if br is None:
        raise ValidationFailed("branch_required")
    return br
