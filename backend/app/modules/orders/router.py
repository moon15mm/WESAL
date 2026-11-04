"""Orders: carts, retailer direct orders, representative orders with retailer approval,
supplier review/offers, fulfillment & delivery, receipt confirmation, collections."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, RepCtx, rep_ctx, retailer_ctx, supplier_ctx
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.schemas import PageParams, paginate
from app.core.storage import save_upload
from app.core.utils import money, next_number, utcnow
from app.models.business import Business
from app.models.catalog import SupplierProduct
from app.models.commissions import Commission
from app.models.enums import (
    ApprovalDecision,
    ApprovalMethod,
    Channel,
    DeliveryStatus,
    FilePurpose,
    OfferStatus,
    OrderChannel,
    OrderStatus as S,
    PaymentStatus,
    SaleUnit,
    VerificationPurpose,
)
from app.models.orders import (
    Cart,
    CartItem,
    DeliveryConfirmation,
    DeliveryRecord,
    Order,
    OrderApproval,
    OrderCollection,
    OrderOffer,
    OrderOfferItem,
    OrderStatusHistory,
    ReturnRequest,
)
from app.models.reps import Representative
from app.modules.catalog.pricing import PricingContext
from app.modules.commissions import service as commissions
from app.modules.common import business_brief, file_url
from app.modules.crm.service import record_order_relationship
from app.modules.notifications.service import members_with_permission, notify
from app.modules.orders import service as svc
from app.modules.orders.service import LineIn

router = APIRouter(tags=["orders"])


# ------------------------------------------------------------------ schemas
class LineSchema(BaseModel):
    offer_id: uuid.UUID
    unit: SaleUnit = SaleUnit.piece
    quantity: int = Field(ge=1, le=100000)


class RetailerOrderIn(BaseModel):
    supplier_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    items: list[LineSchema] = Field(min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    submit: bool = True


class RepOrderIn(BaseModel):
    retailer_id: uuid.UUID
    branch_id: uuid.UUID | None = None
    supplier_id: uuid.UUID
    items: list[LineSchema] = Field(min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)
    visit_id: uuid.UUID | None = None
    submit: bool = True


class ItemsUpdateIn(BaseModel):
    items: list[LineSchema] = Field(min_length=1, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    version: int
    snapshot_hash: str = Field(min_length=64, max_length=64)
    comment: str | None = Field(default=None, max_length=2000)
    otp_code: str | None = Field(default=None, max_length=6)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class OfferLineIn(BaseModel):
    order_item_id: uuid.UUID
    quantity: int = Field(ge=0, le=100000)
    unit_price: Decimal = Field(ge=0, le=1_000_000)
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class OfferIn(BaseModel):
    items: list[OfferLineIn] = Field(min_length=1, max_length=300)
    delivery_fee: Decimal | None = Field(default=None, ge=0, le=100000)
    expected_delivery_date: date | None = None
    valid_until: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AcceptIn(BaseModel):
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class DispatchIn(BaseModel):
    driver_name: str | None = Field(default=None, max_length=160)
    driver_phone: str | None = Field(default=None, max_length=20)
    vehicle_plate: str | None = Field(default=None, max_length=20)
    scheduled_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ReceivedLineIn(BaseModel):
    order_item_id: uuid.UUID
    received_qty: int = Field(ge=0)
    damaged_qty: int = Field(default=0, ge=0)


class ConfirmIn(BaseModel):
    items: list[ReceivedLineIn] | None = None  # omitted = everything received in full
    receiver_name: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=2000)


class CollectionIn(BaseModel):
    amount: Decimal = Field(gt=0, le=100_000_000)
    method: Literal["cash", "bank_transfer", "cheque", "pos", "other"]
    reference: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)


# ------------------------------------------------------------------ serialization
def allowed_actions(o: Order, side: str, perms: set[str]) -> list[str]:
    s = o.status
    acts: list[str] = []
    if side == "retailer":
        if s == S.draft and o.channel == OrderChannel.direct and "retailer.orders.create" in perms:
            acts += ["edit", "submit", "cancel"]
        if s == S.pending_retailer_approval and "retailer.orders.approve" in perms:
            acts += ["approve", "reject", "request_changes", "edit"]
        if s == S.quoted and "retailer.orders.approve" in perms:
            acts += ["accept_offer", "reject_offer"]
        if s == S.awaiting_retailer_approval and "retailer.orders.approve" in perms:
            acts += ["approve_change", "reject_change"]
        if s in (S.new, S.supplier_review, S.quoted, S.approved) and "retailer.orders.cancel" in perms:
            acts.append("cancel")
        if s in (S.out_for_delivery, S.delivered) and "retailer.deliveries.confirm" in perms:
            acts.append("confirm_delivery")
        if s in (S.completed, S.partially_returned, S.delivered) and "retailer.returns.manage" in perms:
            acts.append("request_return")
        if s in (S.delivered, S.completed, S.partially_returned) and "retailer.complaints.manage" in perms:
            acts.append("dispute")
        if s in (S.completed, S.partially_returned, S.fully_returned) and "retailer.ratings.create" in perms:
            acts.append("rate")
        if "retailer.orders.create" in perms and s not in (S.draft,):
            acts.append("reorder")
    elif side == "supplier":
        if s == S.new and "supplier.orders.manage" in perms:
            acts += ["start_review", "accept", "offer", "reject"]
        if s == S.supplier_review and "supplier.orders.manage" in perms:
            acts += ["accept", "offer", "reject"]
        if s == S.quoted and "supplier.orders.manage" in perms:
            acts.append("revise_offer")
        if s in (S.approved, S.preparing) and "supplier.orders.manage" in perms:
            acts += ["modify", "cancel"]
        if s == S.approved and "supplier.fulfillment.manage" in perms:
            acts.append("prepare")
        if s == S.preparing and "supplier.fulfillment.manage" in perms:
            acts.append("ready")
        if s == S.ready and "supplier.fulfillment.manage" in perms:
            acts.append("dispatch")
        if s == S.out_for_delivery and "supplier.fulfillment.manage" in perms:
            acts.append("deliver")
        if s in svc.SALES_STATUSES and "supplier.collections.manage" in perms and o.payment_status != PaymentStatus.paid:
            acts.append("record_collection")
        if s in svc.SALES_STATUSES and "supplier.orders.manage" in perms:
            acts.append("upload_invoice")
    elif side == "rep":
        if s == S.draft:
            acts += ["edit", "submit", "cancel"]
        if s == S.pending_retailer_approval:
            acts.append("withdraw")
    return acts


def order_out(db: Session, o: Order, locale: str, side: str, perms: set[str] = frozenset(), detail: bool = False) -> dict:
    out = {
        "id": str(o.id), "number": o.number, "status": o.status.value, "channel": o.channel.value,
        "retailer": business_brief(o.retailer, locale), "supplier": business_brief(o.supplier, locale),
        "branch": {"id": str(o.branch.id), "name": o.branch.name, "district": o.branch.district,
                   "address_line": o.branch.address_line, "phone": o.branch.phone} if o.branch else None,
        "representative": {"id": str(o.representative.id), "display_name": o.representative.display_name}
        if o.representative else None,
        "currency": o.currency, "subtotal": o.subtotal, "discount_total": o.discount_total, "delivery_fee": o.delivery_fee,
        "vat_rate": o.vat_rate, "vat_total": o.vat_total, "total": o.total, "version": o.version,
        "approved_version": o.approved_version, "payment_status": o.payment_status.value, "paid_amount": o.paid_amount,
        "items_count": len(o.items), "notes": o.notes, "supplier_notes": o.supplier_notes,
        "expected_delivery_date": o.expected_delivery_date, "status_reason": o.status_reason,
        "submitted_at": o.submitted_at, "approved_at": o.approved_at, "delivered_at": o.delivered_at,
        "completed_at": o.completed_at, "created_at": o.created_at, "updated_at": o.updated_at,
        "invoice_number": o.invoice_number, "invoice_url": file_url(o.invoice_file_id),
        "actions": allowed_actions(o, side, set(perms)),
    }
    if not detail:
        return out
    out["items"] = [{"id": str(i.id), "offer_id": str(i.supplier_product_id), "product_id": str(i.product_id),
                     "name": i.name_ar if locale == "ar" else i.name_en, "name_ar": i.name_ar, "name_en": i.name_en,
                     "sku": i.sku, "unit": i.unit.value, "pieces_per_unit": i.pieces_per_unit, "quantity": i.quantity,
                     "list_unit_price": i.list_unit_price, "unit_price": i.unit_price, "discount": i.discount,
                     "line_total": i.line_total, "vat_amount": i.vat_amount, "delivered_qty": i.delivered_qty,
                     "returned_qty": i.returned_qty} for i in o.items]
    out["history"] = [{"from": h.from_status, "to": h.to_status, "reason": h.reason, "actor_role": h.actor_role,
                       "version": h.version, "at": h.created_at}
                      for h in db.scalars(select(OrderStatusHistory).where(OrderStatusHistory.order_id == o.id)
                                          .order_by(OrderStatusHistory.created_at))]
    approvals = db.scalars(select(OrderApproval).where(OrderApproval.order_id == o.id).order_by(OrderApproval.requested_at)).all()
    out["approvals"] = [{"id": str(a.id), "version": a.version, "kind": a.kind, "decision": a.decision.value,
                         "requested_at": a.requested_at, "opened_at": a.opened_at, "decided_at": a.decided_at,
                         "method": a.method.value if a.method else None, "comment": a.comment,
                         "snapshot_hash": a.snapshot_hash} for a in approvals]
    pend = next((a for a in reversed(approvals) if a.decision == ApprovalDecision.pending), None)
    out["pending_approval"] = {"id": str(pend.id), "version": pend.version, "kind": pend.kind,
                               "snapshot_hash": pend.snapshot_hash, "snapshot": pend.snapshot} if pend else None
    offers = db.scalars(select(OrderOffer).where(OrderOffer.order_id == o.id).order_by(OrderOffer.created_at)).all()
    out["offers"] = [{"id": str(f.id), "version": f.version, "status": f.status.value, "subtotal": f.subtotal, "total": f.total,
                      "delivery_fee": f.delivery_fee, "valid_until": f.valid_until, "notes": f.notes,
                      "expected_delivery_date": f.expected_delivery_date, "created_at": f.created_at,
                      "items": [{"order_item_id": str(x.order_item_id), "quantity": x.quantity, "unit_price": x.unit_price,
                                 "discount": x.discount} for x in f.items]} for f in offers]
    d = db.scalar(select(DeliveryRecord).where(DeliveryRecord.order_id == o.id))
    out["delivery"] = None if d is None else {
        "status": d.status.value, "scheduled_date": d.scheduled_date, "prepared_at": d.prepared_at, "ready_at": d.ready_at,
        "dispatched_at": d.dispatched_at, "delivered_at": d.delivered_at, "driver_name": d.driver_name,
        "driver_phone": d.driver_phone, "vehicle_plate": d.vehicle_plate, "proof_url": file_url(d.proof_file_id), "notes": d.notes}
    conf = db.scalars(select(DeliveryConfirmation).where(DeliveryConfirmation.order_id == o.id)).all()
    out["confirmations"] = [{"receiver_name": c.receiver_name, "items": c.items, "has_shortage": c.has_shortage,
                             "notes": c.notes, "created_at": c.created_at} for c in conf]
    if side == "supplier" or side == "retailer":
        cols = db.scalars(select(OrderCollection).where(OrderCollection.order_id == o.id).order_by(OrderCollection.collected_at)).all()
        out["collections"] = [{"amount": c.amount, "method": c.method, "reference": c.reference, "collected_at": c.collected_at,
                               "proof_url": file_url(c.proof_file_id)} for c in cols]
    rets = db.scalars(select(ReturnRequest).where(ReturnRequest.order_id == o.id)).all()
    out["returns"] = [{"id": str(r.id), "number": r.number, "status": r.status.value, "total_value": r.total_value} for r in rets]
    if side in ("supplier", "rep") and o.representative_id:
        c = db.scalar(select(Commission).where(Commission.order_id == o.id))
        out["commission"] = {"id": str(c.id), "status": c.status.value, "amount": c.amount} if c else None
    return out


# ------------------------------------------------------------------ helpers
def _notify_retailer(db, o: Order, event: str, perm: str = "retailer.orders.view") -> None:
    users = members_with_permission(db, o.retailer_id, perm)
    notify(db, users, event, {"number": o.number, "supplier": o.supplier.trade_name_ar, "total": str(o.total)},
           link=f"/app/store/orders/{o.id}", entity_type="order", entity_id=o.id,
           dedupe_key=f"order:{o.id}:{event}:{o.version}:{o.status.value}")


def _notify_supplier(db, o: Order, event: str) -> None:
    users = members_with_permission(db, o.supplier_id, "supplier.orders.view")
    notify(db, users, event, {"number": o.number, "retailer": o.retailer.trade_name_ar, "total": str(o.total)},
           link=f"/app/supplier/orders/{o.id}", entity_type="order", entity_id=o.id,
           dedupe_key=f"order:{o.id}:{event}:{o.version}:{o.status.value}")


def _notify_rep(db, o: Order, event: str) -> None:
    if not o.representative_id:
        return
    with system_context(db):
        rep = db.get(Representative, o.representative_id)
    notify(db, [rep.user_id], event, {"number": o.number, "retailer": o.retailer.trade_name_ar, "total": str(o.total)},
           link=f"/app/rep/orders/{o.id}", entity_type="order", entity_id=o.id,
           dedupe_key=f"order:{o.id}:{event}:{o.version}:{o.status.value}")


def _pricing(db: Session, o: Order) -> PricingContext:
    city = o.branch.city_id if o.branch else None
    return PricingContext(db, o.supplier_id, o.retailer_id, city)


def _fill(db: Session, o: Order, lines: list[LineSchema], supplier: Business) -> None:
    city = o.branch.city_id if o.branch else None
    cov = svc.coverage_for(db, o.supplier_id, city, o.branch.district if o.branch else None)
    o.city_id = city
    svc.build_items(db, o, [LineIn(l.offer_id, l.unit, l.quantity) for l in lines], pricing=_pricing(db, o))
    svc.recompute_totals(o, supplier, delivery_fee=cov.delivery_fee if cov else Decimal("0"))


def _on_approved(db: Session, o: Order) -> None:
    record_order_relationship(db, o)
    commissions.on_order_event(db, o, "approved")


def _retailer_order(db: Session, ctx: BusinessCtx, oid: uuid.UUID) -> Order:
    o = db.get(Order, oid)
    if o is None or o.retailer_id != ctx.business_id:
        raise NotFound()
    if ctx.member.branch_id and o.branch_id != ctx.member.branch_id:
        raise NotFound()  # branch-scoped staff only see their branch
    return o


def _supplier_order(db: Session, ctx: BusinessCtx, oid: uuid.UUID) -> Order:
    o = db.get(Order, oid)
    if o is None or o.supplier_id != ctx.business_id or o.status in (S.draft, S.pending_retailer_approval):
        raise NotFound()  # suppliers never see orders the retailer has not approved/submitted
    return o


def _rep_order(db: Session, ctx: RepCtx, oid: uuid.UUID) -> Order:
    o = db.get(Order, oid)
    if o is None or o.representative_id != ctx.rep.id:
        raise NotFound()
    return o


def _list(db: Session, stmt, params: PageParams, status, q, date_from, date_to, locale, side, perms):
    if status:
        stmt = stmt.where(Order.status.in_(status.split(",")))
    if q:
        stmt = stmt.where(Order.number.ilike(f"%{q}%"))
    if date_from:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.created_at <= date_to)
    return paginate(db, stmt.order_by(Order.created_at.desc()), params, lambda o: order_out(db, o, locale, side, perms))


def _check_decision(db: Session, o: Order, data: DecisionIn, ctx: BusinessCtx, request: Request) -> OrderApproval:
    ap = svc.pending_approval(db, o)
    if ap is None:
        raise Conflict("no_pending_approval")
    if data.version != o.version or data.version != ap.version or data.snapshot_hash != ap.snapshot_hash:
        raise Conflict("order_version_changed")  # the retailer must approve exactly what they saw
    if svc.snapshot_hash(svc.snapshot(o)) != ap.snapshot_hash:
        raise Conflict("order_version_changed")
    method = ApprovalMethod.session
    if (ctx.business.settings or {}).get("approval_otp"):
        from app.modules.auth.service import consume_code

        if not data.otp_code:
            raise ValidationFailed("otp_required")
        consume_code(db, ctx.user.phone or "", VerificationPurpose.order_approval, data.otp_code, reference_id=str(o.id))
        method = ApprovalMethod.otp
    ap.decided_at = utcnow()
    ap.decided_by = ctx.user.id
    ap.method = method
    ap.comment = data.comment
    ap.ip = getattr(request.state, "client_ip", None)
    return ap


# ------------------------------------------------------------------ carts (retailer)
class CartLineIn(BaseModel):
    offer_id: uuid.UUID
    unit: SaleUnit = SaleUnit.piece
    quantity: int = Field(ge=0, le=100000)


def cart_out(db: Session, cart: Cart, ctx: BusinessCtx) -> dict:
    supplier = db.get(Business, cart.supplier_id)
    offers = {sp.id: sp for sp in db.scalars(select(SupplierProduct).where(
        SupplierProduct.id.in_([i.supplier_product_id for i in cart.items])))} if cart.items else {}
    pc = PricingContext(db, cart.supplier_id, ctx.business_id, ctx.business.city_id)
    lines, subtotal, discount = [], Decimal("0"), Decimal("0")
    for i in cart.items:
        sp = offers.get(i.supplier_product_id)
        if sp is None:
            continue
        p = pc.price(sp, i.unit, i.quantity)
        gross = money(p.list_unit_price * i.quantity)
        disc = money(p.discount_per_unit * i.quantity)
        subtotal += gross
        discount += disc
        lines.append({"offer_id": str(sp.id), "product_id": str(sp.product_id),
                      "name": sp.product.name_ar if ctx.principal.locale == "ar" else sp.product.name_en,
                      "image_url": file_url(sp.product.image_file_id), "unit": i.unit.value, "quantity": i.quantity,
                      "pieces_per_unit": p.pieces_per_unit, "unit_price": p.list_unit_price, "discount": disc,
                      "line_total": money(gross - disc), "availability": sp.availability.value,
                      "min_order_qty": sp.min_order_qty, "is_active": sp.is_active})
    return {"id": str(cart.id), "supplier": business_brief(supplier, ctx.principal.locale), "branch_id": str(cart.branch_id) if cart.branch_id else None,
            "items": lines, "subtotal": money(subtotal), "discount_total": money(discount), "net": money(subtotal - discount),
            "min_order_value": supplier.min_order_value, "notes": cart.notes, "updated_at": cart.updated_at}


@router.get("/retailer/carts")
def list_carts(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    carts = db.scalars(select(Cart).where(Cart.user_id == ctx.user.id, Cart.retailer_id == ctx.business_id)).all()
    return [cart_out(db, c, ctx) for c in carts if c.items]


@router.put("/retailer/carts/{supplier_id}/items")
def set_cart_item(supplier_id: uuid.UUID, data: CartLineIn, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    svc.supplier_for_orders(db, supplier_id)
    sp = db.get(SupplierProduct, data.offer_id)
    if sp is None or sp.supplier_id != supplier_id or not sp.is_active:
        raise ValidationFailed("invalid_offer")
    cart = db.scalar(select(Cart).where(Cart.user_id == ctx.user.id, Cart.retailer_id == ctx.business_id,
                                        Cart.supplier_id == supplier_id))
    if cart is None:
        cart = Cart(user_id=ctx.user.id, retailer_id=ctx.business_id, supplier_id=supplier_id, branch_id=ctx.member.branch_id)
        db.add(cart)
        db.flush()
    item = next((i for i in cart.items if i.supplier_product_id == sp.id and i.unit == data.unit), None)
    if data.quantity == 0:
        if item:
            cart.items.remove(item)
    elif item:
        item.quantity = data.quantity
    else:
        if len(cart.items) >= 300:
            raise ValidationFailed("too_many_items")
        cart.items.append(CartItem(supplier_product_id=sp.id, unit=data.unit, quantity=data.quantity))
    cart.updated_at = utcnow()
    db.commit()
    db.refresh(cart)
    return cart_out(db, cart, ctx)


@router.delete("/retailer/carts/{supplier_id}")
def clear_cart(supplier_id: uuid.UUID, db: Session = Depends(get_db),
               ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    cart = db.scalar(select(Cart).where(Cart.user_id == ctx.user.id, Cart.retailer_id == ctx.business_id,
                                        Cart.supplier_id == supplier_id))
    if cart:
        db.delete(cart)
        db.commit()
    return {"ok": True}


class CheckoutIn(BaseModel):
    branch_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/retailer/carts/{supplier_id}/checkout", status_code=201)
def checkout(supplier_id: uuid.UUID, data: CheckoutIn, request: Request, db: Session = Depends(get_db),
             ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    cart = db.scalar(select(Cart).where(Cart.user_id == ctx.user.id, Cart.retailer_id == ctx.business_id,
                                        Cart.supplier_id == supplier_id))
    if cart is None or not cart.items:
        raise ValidationFailed("cart_empty")
    body = RetailerOrderIn(supplier_id=supplier_id, branch_id=data.branch_id or cart.branch_id, notes=data.notes,
                           items=[LineSchema(offer_id=i.supplier_product_id, unit=i.unit, quantity=i.quantity) for i in cart.items])
    result = _create_retailer_order(body, request, db, ctx)
    db.delete(cart)
    db.commit()
    return result


# ------------------------------------------------------------------ retailer orders
@router.post("/retailer/orders", status_code=201)
def create_retailer_order(data: RetailerOrderIn, request: Request, db: Session = Depends(get_db),
                          ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    result = _create_retailer_order(data, request, db, ctx)
    db.commit()
    return result


def _create_retailer_order(data: RetailerOrderIn, request: Request, db: Session, ctx: BusinessCtx) -> dict:
    ratelimit.hit(f"order-create:{ctx.user.id}", 60, 3600)
    idem = request.headers.get("idempotency-key")
    if idem:
        existing = db.scalar(select(Order).where(Order.created_by_user_id == ctx.user.id, Order.idempotency_key == idem[:80]))
        if existing:
            return order_out(db, existing, ctx.principal.locale, "retailer", ctx.perms, detail=True)
    if not (ctx.user.phone_verified_at or ctx.user.email_verified_at):
        raise Forbidden("contact_verification_required")
    supplier = svc.supplier_for_orders(db, data.supplier_id)
    branch_id = data.branch_id or ctx.member.branch_id
    if ctx.member.branch_id and branch_id != ctx.member.branch_id:
        raise Forbidden("branch_not_allowed")
    branch = svc.branch_for(db, ctx.business_id, branch_id)
    o = Order(number=next_number(db, "WSL"), retailer_id=ctx.business_id, branch_id=branch.id, supplier_id=supplier.id,
              channel=OrderChannel.direct, status=S.draft, created_by_user_id=ctx.user.id, notes=data.notes,
              currency=supplier.settings.get("currency", "SAR") if supplier.settings else "SAR",
              idempotency_key=idem[:80] if idem else None)
    o.branch = branch
    db.add(o)
    db.flush()
    _fill(db, o, data.items, supplier)
    db.add(OrderStatusHistory(order_id=o.id, to_status=S.draft.value, actor_user_id=ctx.user.id, actor_role="retailer",
                              version=o.version))
    if data.submit:
        cov = svc.coverage_for(db, supplier.id, branch.city_id, branch.district)
        svc.check_minimums(o, supplier, cov)
        svc.transition(db, o, S.new, ctx.user.id, "retailer")
        _notify_supplier(db, o, "order_new")
    audit(db, "order.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"total": o.total, "status": o.status.value}, request=request)
    db.flush()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.get("/retailer/orders")
def retailer_orders(status: str | None = None, q: str | None = None, date_from: datetime | None = None,
                    date_to: datetime | None = None, branch_id: uuid.UUID | None = None, params: PageParams = Depends(),
                    db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.view"))):
    stmt = select(Order).where(Order.retailer_id == ctx.business_id)
    if ctx.member.branch_id:
        stmt = stmt.where(Order.branch_id == ctx.member.branch_id)
    elif branch_id:
        stmt = stmt.where(Order.branch_id == branch_id)
    return _list(db, stmt, params, status, q, date_from, date_to, ctx.principal.locale, "retailer", ctx.perms)


@router.get("/retailer/orders/{oid}")
def retailer_order(oid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.view"))):
    o = _retailer_order(db, ctx, oid)
    ap = svc.pending_approval(db, o)
    if ap and ap.opened_at is None:
        ap.opened_at, ap.opened_by = utcnow(), ctx.user.id
        db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.put("/retailer/orders/{oid}/items")
def retailer_edit(oid: uuid.UUID, data: ItemsUpdateIn, request: Request, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    """Edit a draft, or adjust a representative's order before approving it (creates a new version)."""
    o = _retailer_order(db, ctx, oid)
    if o.status == S.pending_retailer_approval:
        ctx.require("retailer.orders.approve")
    elif not (o.status == S.draft and o.channel == OrderChannel.direct):
        raise Conflict("order_not_editable")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    _fill(db, o, data.items, supplier)
    if data.notes is not None:
        o.notes = data.notes
    o.version += 1
    if o.status == S.pending_retailer_approval:
        svc.open_approval(db, o, "rep_order", ctx.user.id)
        _notify_rep(db, o, "order_updated")
    audit(db, "order.edit", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"version": o.version, "total": o.total}, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/submit")
def retailer_submit(oid: uuid.UUID, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    o = _retailer_order(db, ctx, oid)
    if o.channel != OrderChannel.direct:
        raise Conflict("order_invalid_transition")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    _fill(db, o, [LineSchema(offer_id=i.supplier_product_id, unit=i.unit, quantity=i.quantity) for i in o.items], supplier)
    cov = svc.coverage_for(db, o.supplier_id, o.branch.city_id if o.branch else None, o.branch.district if o.branch else None)
    svc.check_minimums(o, supplier, cov)
    svc.transition(db, o, S.new, ctx.user.id, "retailer")
    _notify_supplier(db, o, "order_new")
    audit(db, "order.submit", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/approval-otp")
def send_approval_otp(oid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    from app.modules.auth.service import issue_code

    o = _retailer_order(db, ctx, oid)
    if not ctx.user.phone or not ctx.user.phone_verified_at:
        raise ValidationFailed("phone_verification_required")
    issue_code(db, ctx.user, Channel.sms, VerificationPurpose.order_approval, reference_id=str(o.id))
    db.commit()
    return {"ok": True}


@router.post("/retailer/orders/{oid}/approve")
def retailer_approve(oid: uuid.UUID, data: DecisionIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    """Approve a representative-created order (exact version)."""
    o = _retailer_order(db, ctx, oid)
    if o.status != S.pending_retailer_approval:
        raise Conflict("order_invalid_transition")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    cov = svc.coverage_for(db, o.supplier_id, o.branch.city_id if o.branch else None, o.branch.district if o.branch else None)
    svc.check_minimums(o, supplier, cov)
    ap = _check_decision(db, o, data, ctx, request)
    ap.decision = ApprovalDecision.approved
    svc.transition(db, o, S.new, ctx.user.id, "retailer", data.comment)
    _notify_supplier(db, o, "order_new")
    _notify_rep(db, o, "order_approved")
    audit(db, "order.retailer_approve", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"version": o.version, "hash": ap.snapshot_hash, "method": ap.method.value}, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


def _retailer_reject_like(oid, data: ReasonIn, request, db, ctx, *, expected: S, to: S, decision: ApprovalDecision,
                          action: str, event: str):
    o = _retailer_order(db, ctx, oid)
    if o.status != expected:
        raise Conflict("order_invalid_transition")
    ap = svc.pending_approval(db, o)
    if ap:
        ap.decision, ap.decided_at, ap.decided_by, ap.comment = decision, utcnow(), ctx.user.id, data.reason
    svc.transition(db, o, to, ctx.user.id, "retailer", data.reason)
    _notify_rep(db, o, event)
    audit(db, f"order.{action}", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, reason=data.reason, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/reject")
def retailer_reject(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    return _retailer_reject_like(oid, data, request, db, ctx, expected=S.pending_retailer_approval, to=S.rejected,
                                 decision=ApprovalDecision.rejected, action="retailer_reject", event="order_rejected")


@router.post("/retailer/orders/{oid}/request-changes")
def retailer_request_changes(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                             ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    return _retailer_reject_like(oid, data, request, db, ctx, expected=S.pending_retailer_approval, to=S.draft,
                                 decision=ApprovalDecision.changes_requested, action="retailer_request_changes",
                                 event="order_changes_requested")


@router.post("/retailer/orders/{oid}/accept-offer")
def accept_offer(oid: uuid.UUID, data: DecisionIn, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    o = _retailer_order(db, ctx, oid)
    if o.status != S.quoted:
        raise Conflict("order_invalid_transition")
    offer = db.scalar(select(OrderOffer).where(OrderOffer.order_id == o.id, OrderOffer.status == OfferStatus.pending))
    if offer is None:
        raise Conflict("no_pending_offer")
    if offer.valid_until and offer.valid_until < utcnow():
        offer.status = OfferStatus.expired
        db.commit()
        raise Conflict("offer_expired")
    ap = _check_decision(db, o, data, ctx, request)
    ap.decision = ApprovalDecision.approved
    offer.status = OfferStatus.accepted
    if offer.expected_delivery_date:
        o.expected_delivery_date = offer.expected_delivery_date
    svc.transition(db, o, S.approved, ctx.user.id, "retailer", data.comment)
    _on_approved(db, o)
    _notify_supplier(db, o, "order_approved")
    _notify_rep(db, o, "order_approved")
    audit(db, "order.accept_offer", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"offer_id": offer.id, "version": o.version}, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/reject-offer")
def reject_offer(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    o = _retailer_order(db, ctx, oid)
    if o.status != S.quoted:
        raise Conflict("order_invalid_transition")
    for f in db.scalars(select(OrderOffer).where(OrderOffer.order_id == o.id, OrderOffer.status == OfferStatus.pending)):
        f.status = OfferStatus.rejected
    ap = svc.pending_approval(db, o)
    if ap:
        ap.decision, ap.decided_at, ap.decided_by, ap.comment = ApprovalDecision.rejected, utcnow(), ctx.user.id, data.reason
    svc.transition(db, o, S.rejected, ctx.user.id, "retailer", data.reason)
    _notify_supplier(db, o, "order_rejected")
    _notify_rep(db, o, "order_rejected")
    audit(db, "order.reject_offer", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, reason=data.reason, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/approve-change")
def approve_change(oid: uuid.UUID, data: DecisionIn, request: Request, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    o = _retailer_order(db, ctx, oid)
    if o.status != S.awaiting_retailer_approval:
        raise Conflict("order_invalid_transition")
    ap = _check_decision(db, o, data, ctx, request)
    ap.decision = ApprovalDecision.approved
    svc.transition(db, o, S.approved, ctx.user.id, "retailer", data.comment)
    commissions.on_order_event(db, o, "approved")
    _notify_supplier(db, o, "order_approved")
    audit(db, "order.approve_change", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"version": o.version}, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/reject-change")
def reject_change(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.approve"))):
    o = _retailer_order(db, ctx, oid)
    if o.status != S.awaiting_retailer_approval:
        raise Conflict("order_invalid_transition")
    ap = svc.pending_approval(db, o)
    if ap:
        ap.decision, ap.decided_at, ap.decided_by, ap.comment = ApprovalDecision.rejected, utcnow(), ctx.user.id, data.reason
    svc.transition(db, o, S.cancelled, ctx.user.id, "retailer", data.reason)
    commissions.on_order_event(db, o, "cancelled")
    _notify_supplier(db, o, "order_cancelled")
    _notify_rep(db, o, "order_cancelled")
    audit(db, "order.reject_change", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, reason=data.reason, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/cancel")
def retailer_cancel(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.cancel"))):
    o = _retailer_order(db, ctx, oid)
    if o.status not in (S.draft, S.new, S.supplier_review, S.quoted, S.approved):
        raise Conflict("order_invalid_transition")
    if o.status == S.draft and o.channel != OrderChannel.direct:
        raise Conflict("order_invalid_transition")
    for f in db.scalars(select(OrderOffer).where(OrderOffer.order_id == o.id, OrderOffer.status == OfferStatus.pending)):
        f.status = OfferStatus.rejected
    svc.transition(db, o, S.cancelled, ctx.user.id, "retailer", data.reason)
    commissions.on_order_event(db, o, "cancelled")
    _notify_supplier(db, o, "order_cancelled")
    _notify_rep(db, o, "order_cancelled")
    audit(db, "order.retailer_cancel", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, reason=data.reason, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/confirm-delivery")
def confirm_delivery(oid: uuid.UUID, data: ConfirmIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(retailer_ctx("retailer.deliveries.confirm"))):
    o = _retailer_order(db, ctx, oid)
    if o.status not in (S.out_for_delivery, S.delivered):
        raise Conflict("order_invalid_transition")
    items = {i.id: i for i in o.items}
    received = {}
    if data.items:
        for line in data.items:
            it = items.get(line.order_item_id)
            if it is None:
                raise ValidationFailed("invalid_item")
            if line.received_qty + line.damaged_qty > it.quantity:
                raise ValidationFailed("received_exceeds_ordered")
            received[it.id] = (line.received_qty, line.damaged_qty)
    shortage = False
    rows = []
    for it in o.items:
        rq, dq = received.get(it.id, (it.quantity, 0))
        it.delivered_qty = rq
        shortage = shortage or rq < it.quantity
        rows.append({"order_item_id": str(it.id), "ordered": it.quantity, "received_qty": rq, "damaged_qty": dq})
    d = db.scalar(select(DeliveryRecord).where(DeliveryRecord.order_id == o.id))
    if d is None:
        d = DeliveryRecord(order_id=o.id)
        db.add(d)
        db.flush()
    d.status = DeliveryStatus.delivered
    d.delivered_at = d.delivered_at or utcnow()
    db.add(DeliveryConfirmation(delivery_id=d.id, order_id=o.id, confirmed_by=ctx.user.id, receiver_name=data.receiver_name,
                                items=rows, has_shortage=shortage, notes=data.notes))
    if o.status == S.out_for_delivery:
        svc.transition(db, o, S.delivered, ctx.user.id, "retailer", "receipt confirmed by store")
        commissions.on_order_event(db, o, "delivered")
    svc.transition(db, o, S.completed, ctx.user.id, "retailer", "shortage recorded" if shortage else None)
    commissions.on_order_event(db, o, "completed")
    _notify_supplier(db, o, "order_completed")
    _notify_rep(db, o, "order_completed")
    audit(db, "order.confirm_delivery", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes={"shortage": shortage, "items": rows}, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "retailer", ctx.perms, detail=True)


@router.post("/retailer/orders/{oid}/reorder")
def reorder(oid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(retailer_ctx("retailer.orders.create"))):
    o = _retailer_order(db, ctx, oid)
    svc.supplier_for_orders(db, o.supplier_id)
    cart = db.scalar(select(Cart).where(Cart.user_id == ctx.user.id, Cart.retailer_id == ctx.business_id,
                                        Cart.supplier_id == o.supplier_id))
    if cart is None:
        cart = Cart(user_id=ctx.user.id, retailer_id=ctx.business_id, supplier_id=o.supplier_id, branch_id=o.branch_id)
        db.add(cart)
        db.flush()
    skipped = 0
    for it in o.items:
        sp = db.get(SupplierProduct, it.supplier_product_id)
        if sp is None or not sp.is_active or sp.availability.value in ("out_of_stock", "discontinued"):
            skipped += 1
            continue
        existing = next((c for c in cart.items if c.supplier_product_id == sp.id and c.unit == it.unit), None)
        if existing:
            existing.quantity = max(existing.quantity, it.quantity)
        else:
            cart.items.append(CartItem(supplier_product_id=sp.id, unit=it.unit, quantity=it.quantity))
    db.commit()
    db.refresh(cart)
    return {"cart": cart_out(db, cart, ctx), "skipped": skipped}


# ------------------------------------------------------------------ representative orders
@router.post("/rep/orders", status_code=201)
def create_rep_order(data: RepOrderIn, request: Request, db: Session = Depends(get_db),
                     ctx: RepCtx = Depends(rep_ctx(require_verified=True))):
    from app.models.catalog import Product
    from app.modules.authorizations.service import require_order_authorization

    ratelimit.hit(f"order-create:{ctx.user.id}", 60, 3600)
    supplier = svc.supplier_for_orders(db, data.supplier_id)
    with system_context(db):
        retailer = db.get(Business, data.retailer_id)
        if retailer is None or retailer.type.value != "retailer" or retailer.status.value != "active":
            raise ValidationFailed("invalid_retailer")
        branch = svc.branch_for(db, retailer.id, data.branch_id)
    offers = db.scalars(select(SupplierProduct).where(SupplierProduct.id.in_([i.offer_id for i in data.items]))).all()
    products = [db.get(Product, sp.product_id) for sp in offers if sp.supplier_id == supplier.id]
    if len(products) != len({i.offer_id for i in data.items}):
        raise ValidationFailed("invalid_offer")
    auth = require_order_authorization(db, ctx.rep.id, supplier.id, products, branch.city_id, branch.district)
    o = Order(number=next_number(db, "WSL"), retailer_id=retailer.id, branch_id=branch.id, supplier_id=supplier.id,
              channel=OrderChannel.representative, status=S.draft, created_by_user_id=ctx.user.id,
              representative_id=ctx.rep.id, authorization_id=auth.id, notes=data.notes, visit_id=data.visit_id)
    o.branch = branch
    db.add(o)
    db.flush()
    with system_context(db):
        _fill(db, o, data.items, supplier)
    db.add(OrderStatusHistory(order_id=o.id, to_status=S.draft.value, actor_user_id=ctx.user.id, actor_role="representative",
                              version=o.version))
    if data.submit:
        _rep_submit(db, o, ctx, supplier, branch)
    audit(db, "order.rep_create", actor_user_id=ctx.user.id, entity_type="order", entity_id=o.id,
          changes={"retailer_id": retailer.id, "supplier_id": supplier.id, "total": o.total, "authorization": auth.number},
          request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "rep", detail=True)


def _rep_submit(db: Session, o: Order, ctx: RepCtx, supplier: Business, branch) -> None:
    cov = svc.coverage_for(db, supplier.id, branch.city_id, branch.district)
    svc.check_minimums(o, supplier, cov)
    svc.transition(db, o, S.pending_retailer_approval, ctx.user.id, "representative")
    svc.open_approval(db, o, "rep_order", ctx.user.id)
    _notify_retailer(db, o, "order_approval_required", "retailer.orders.approve")


@router.get("/rep/orders")
def rep_orders(status: str | None = None, q: str | None = None, date_from: datetime | None = None,
               date_to: datetime | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
               ctx: RepCtx = Depends(rep_ctx())):
    stmt = select(Order).where(Order.representative_id == ctx.rep.id)
    return _list(db, stmt, params, status, q, date_from, date_to, ctx.principal.locale, "rep", set())


@router.get("/rep/orders/{oid}")
def rep_order(oid: uuid.UUID, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    return order_out(db, _rep_order(db, ctx, oid), ctx.principal.locale, "rep", detail=True)


@router.put("/rep/orders/{oid}/items")
def rep_edit(oid: uuid.UUID, data: ItemsUpdateIn, request: Request, db: Session = Depends(get_db),
             ctx: RepCtx = Depends(rep_ctx(require_verified=True))):
    from app.models.catalog import Product
    from app.modules.authorizations.service import require_order_authorization

    o = _rep_order(db, ctx, oid)
    if o.status != S.draft:
        raise Conflict("order_not_editable")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    offers = db.scalars(select(SupplierProduct).where(SupplierProduct.id.in_([i.offer_id for i in data.items]))).all()
    products = [db.get(Product, sp.product_id) for sp in offers if sp.supplier_id == supplier.id]
    auth = require_order_authorization(db, ctx.rep.id, supplier.id, products, o.branch.city_id, o.branch.district)
    o.authorization_id = auth.id
    with system_context(db):
        _fill(db, o, data.items, supplier)
    if data.notes is not None:
        o.notes = data.notes
    o.version += 1
    db.commit()
    return order_out(db, o, ctx.principal.locale, "rep", detail=True)


@router.post("/rep/orders/{oid}/submit")
def rep_submit(oid: uuid.UUID, request: Request, db: Session = Depends(get_db),
               ctx: RepCtx = Depends(rep_ctx(require_verified=True))):
    from app.models.catalog import Product
    from app.modules.authorizations.service import require_order_authorization

    o = _rep_order(db, ctx, oid)
    if o.status != S.draft:
        raise Conflict("order_invalid_transition")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    products = [db.get(Product, i.product_id) for i in o.items]
    require_order_authorization(db, ctx.rep.id, supplier.id, products, o.branch.city_id, o.branch.district)
    with system_context(db):
        _fill(db, o, [LineSchema(offer_id=i.supplier_product_id, unit=i.unit, quantity=i.quantity) for i in o.items], supplier)
    o.version += 1
    _rep_submit(db, o, ctx, supplier, o.branch)
    audit(db, "order.rep_submit", actor_user_id=ctx.user.id, entity_type="order", entity_id=o.id, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "rep", detail=True)


@router.post("/rep/orders/{oid}/withdraw")
def rep_withdraw(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db), ctx: RepCtx = Depends(rep_ctx())):
    o = _rep_order(db, ctx, oid)
    if o.status not in (S.pending_retailer_approval, S.draft):
        raise Conflict("order_invalid_transition")
    ap = svc.pending_approval(db, o)
    if ap:
        ap.decision, ap.decided_at = ApprovalDecision.superseded, utcnow()
    svc.transition(db, o, S.cancelled, ctx.user.id, "representative", data.reason)
    audit(db, "order.rep_withdraw", actor_user_id=ctx.user.id, entity_type="order", entity_id=o.id, reason=data.reason,
          request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "rep", detail=True)


# ------------------------------------------------------------------ supplier orders
@router.get("/supplier/orders")
def supplier_orders(status: str | None = None, q: str | None = None, date_from: datetime | None = None,
                    date_to: datetime | None = None, retailer_id: uuid.UUID | None = None,
                    representative_id: uuid.UUID | None = None, params: PageParams = Depends(),
                    db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.view"))):
    stmt = select(Order).where(Order.supplier_id == ctx.business_id,
                               Order.status.notin_([S.draft, S.pending_retailer_approval]))
    if retailer_id:
        stmt = stmt.where(Order.retailer_id == retailer_id)
    if representative_id:
        stmt = stmt.where(Order.representative_id == representative_id)
    return _list(db, stmt, params, status, q, date_from, date_to, ctx.principal.locale, "supplier", ctx.perms)


@router.get("/supplier/orders/{oid}")
def supplier_order(oid: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.view"))):
    return order_out(db, _supplier_order(db, ctx, oid), ctx.principal.locale, "supplier", ctx.perms, detail=True)


def _sup_done(db, o, ctx, action, request, changes=None, reason=None):
    audit(db, f"order.{action}", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="order",
          entity_id=o.id, changes=changes, reason=reason, request=request)
    db.commit()
    return order_out(db, o, ctx.principal.locale, "supplier", ctx.perms, detail=True)


@router.post("/supplier/orders/{oid}/start-review")
def start_review(oid: uuid.UUID, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    o = _supplier_order(db, ctx, oid)
    svc.transition(db, o, S.supplier_review, ctx.user.id, "supplier")
    return _sup_done(db, o, ctx, "start_review", request)


@router.post("/supplier/orders/{oid}/accept")
def supplier_accept(oid: uuid.UUID, data: AcceptIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    """Accept the order at the prices/quantities the retailer already approved."""
    o = _supplier_order(db, ctx, oid)
    if o.status not in (S.new, S.supplier_review):
        raise Conflict("order_invalid_transition")
    o.expected_delivery_date = data.expected_delivery_date
    o.supplier_notes = data.notes
    svc.transition(db, o, S.approved, ctx.user.id, "supplier")
    _on_approved(db, o)
    with system_context(db):
        db.add(DeliveryRecord(order_id=o.id, scheduled_date=data.expected_delivery_date))
    _notify_retailer(db, o, "order_approved")
    _notify_rep(db, o, "order_approved")
    return _sup_done(db, o, ctx, "supplier_accept", request)


@router.post("/supplier/orders/{oid}/offer")
def supplier_offer(oid: uuid.UUID, data: OfferIn, request: Request, db: Session = Depends(get_db),
                   ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    """Submit a price offer (quotation). The order's lines take the offered values and the
    retailer must approve this exact version."""
    o = _supplier_order(db, ctx, oid)
    if o.status not in (S.new, S.supplier_review, S.quoted):
        raise Conflict("order_invalid_transition")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    items = {i.id: i for i in o.items}
    offered = {l.order_item_id: l for l in data.items}
    if set(offered) - set(items):
        raise ValidationFailed("invalid_item")
    for prev in db.scalars(select(OrderOffer).where(OrderOffer.order_id == o.id, OrderOffer.status == OfferStatus.pending)):
        prev.status = OfferStatus.superseded
    lines: list[LineIn] = []
    for it in o.items:
        l = offered.get(it.id)
        qty = l.quantity if l else it.quantity
        if qty == 0:
            continue
        lines.append(LineIn(it.supplier_product_id, it.unit, qty, unit_price=l.unit_price if l else it.unit_price,
                            discount=l.discount if l else it.discount))
    if not lines:
        raise ValidationFailed("order_empty")
    with system_context(db):
        svc.build_items(db, o, lines, pricing=_pricing(db, o), allow_price_override=True)
    svc.recompute_totals(o, supplier, delivery_fee=data.delivery_fee if data.delivery_fee is not None else o.delivery_fee)
    o.version += 1
    db.flush()
    offer = OrderOffer(order_id=o.id, version=o.version, created_by=ctx.user.id, delivery_fee=o.delivery_fee,
                       expected_delivery_date=data.expected_delivery_date, valid_until=data.valid_until, notes=data.notes,
                       subtotal=o.subtotal, total=o.total)
    db.add(offer)
    db.flush()
    for it in o.items:
        offer.items.append(OrderOfferItem(order_item_id=it.id, quantity=it.quantity, unit_price=it.unit_price, discount=it.discount))
    if o.status == S.quoted:
        svc.transition(db, o, S.supplier_review, ctx.user.id, "supplier", "offer revised")
    svc.transition(db, o, S.quoted, ctx.user.id, "supplier")
    with system_context(db):
        svc.open_approval(db, o, "offer", ctx.user.id)
    _notify_retailer(db, o, "order_offer", "retailer.orders.approve")
    return _sup_done(db, o, ctx, "supplier_offer", request, changes={"version": o.version, "total": o.total})


@router.post("/supplier/orders/{oid}/reject")
def supplier_reject(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    o = _supplier_order(db, ctx, oid)
    if o.status not in (S.new, S.supplier_review):
        raise Conflict("order_invalid_transition")
    svc.transition(db, o, S.rejected, ctx.user.id, "supplier", data.reason)
    _notify_retailer(db, o, "order_rejected")
    _notify_rep(db, o, "order_rejected")
    return _sup_done(db, o, ctx, "supplier_reject", request, reason=data.reason)


@router.post("/supplier/orders/{oid}/modify")
def supplier_modify(oid: uuid.UUID, data: OfferIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    """Change quantities/prices after approval (e.g. stock shortage) → retailer must re-approve."""
    o = _supplier_order(db, ctx, oid)
    if o.status not in (S.approved, S.preparing):
        raise Conflict("order_invalid_transition")
    supplier = svc.supplier_for_orders(db, o.supplier_id)
    items = {i.id: i for i in o.items}
    changed = {l.order_item_id: l for l in data.items}
    if set(changed) - set(items):
        raise ValidationFailed("invalid_item")
    lines = []
    for it in o.items:
        l = changed.get(it.id)
        qty = l.quantity if l else it.quantity
        if qty:
            lines.append(LineIn(it.supplier_product_id, it.unit, qty, unit_price=l.unit_price if l else it.unit_price,
                                discount=l.discount if l else it.discount))
    before = svc.snapshot_hash(svc.snapshot(o))
    with system_context(db):
        svc.build_items(db, o, lines, pricing=_pricing(db, o), allow_price_override=True)
    svc.recompute_totals(o, supplier, delivery_fee=data.delivery_fee if data.delivery_fee is not None else o.delivery_fee)
    if svc.snapshot_hash({**svc.snapshot(o), "version": o.version}) == before:
        raise ValidationFailed("no_changes")
    o.version += 1
    svc.transition(db, o, S.awaiting_retailer_approval, ctx.user.id, "supplier", data.notes)
    with system_context(db):
        svc.open_approval(db, o, "change", ctx.user.id)
    _notify_retailer(db, o, "order_approval_required", "retailer.orders.approve")
    return _sup_done(db, o, ctx, "supplier_modify", request, changes={"version": o.version, "total": o.total})


@router.post("/supplier/orders/{oid}/cancel")
def supplier_cancel(oid: uuid.UUID, data: ReasonIn, request: Request, db: Session = Depends(get_db),
                    ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    o = _supplier_order(db, ctx, oid)
    if o.status not in (S.approved, S.preparing, S.ready):
        raise Conflict("order_invalid_transition")
    svc.transition(db, o, S.cancelled, ctx.user.id, "supplier", data.reason)
    commissions.on_order_event(db, o, "cancelled")
    _notify_retailer(db, o, "order_cancelled")
    _notify_rep(db, o, "order_cancelled")
    return _sup_done(db, o, ctx, "supplier_cancel", request, reason=data.reason)


def _delivery(db: Session, o: Order) -> DeliveryRecord:
    with system_context(db):
        d = db.scalar(select(DeliveryRecord).where(DeliveryRecord.order_id == o.id))
        if d is None:
            d = DeliveryRecord(order_id=o.id)
            db.add(d)
            db.flush()
    return d


@router.post("/supplier/orders/{oid}/prepare")
def prepare(oid: uuid.UUID, request: Request, db: Session = Depends(get_db),
            ctx: BusinessCtx = Depends(supplier_ctx("supplier.fulfillment.manage"))):
    o = _supplier_order(db, ctx, oid)
    svc.transition(db, o, S.preparing, ctx.user.id, "supplier")
    d = _delivery(db, o)
    d.status, d.prepared_at = DeliveryStatus.preparing, utcnow()
    _notify_retailer(db, o, "order_preparing")
    return _sup_done(db, o, ctx, "prepare", request)


@router.post("/supplier/orders/{oid}/ready")
def ready(oid: uuid.UUID, request: Request, db: Session = Depends(get_db),
          ctx: BusinessCtx = Depends(supplier_ctx("supplier.fulfillment.manage"))):
    o = _supplier_order(db, ctx, oid)
    svc.transition(db, o, S.ready, ctx.user.id, "supplier")
    d = _delivery(db, o)
    d.status, d.ready_at = DeliveryStatus.ready, utcnow()
    return _sup_done(db, o, ctx, "ready", request)


@router.post("/supplier/orders/{oid}/dispatch")
def dispatch(oid: uuid.UUID, data: DispatchIn, request: Request, db: Session = Depends(get_db),
             ctx: BusinessCtx = Depends(supplier_ctx("supplier.fulfillment.manage"))):
    o = _supplier_order(db, ctx, oid)
    svc.transition(db, o, S.out_for_delivery, ctx.user.id, "supplier")
    d = _delivery(db, o)
    d.status, d.dispatched_at = DeliveryStatus.out_for_delivery, utcnow()
    d.driver_name, d.driver_phone, d.vehicle_plate = data.driver_name, data.driver_phone, data.vehicle_plate
    d.scheduled_date = data.scheduled_date or d.scheduled_date
    d.notes = data.notes
    _notify_retailer(db, o, "order_out_for_delivery")
    return _sup_done(db, o, ctx, "dispatch", request, changes=data.model_dump())


@router.post("/supplier/orders/{oid}/deliver")
def deliver(oid: uuid.UUID, request: Request, notes: str | None = Form(None), proof: UploadFile | None = File(None),
            db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.fulfillment.manage"))):
    """Supplier marks as delivered (optionally with proof). The store then confirms receipt;
    without a response the order auto-completes after the configured number of days."""
    o = _supplier_order(db, ctx, oid)
    svc.transition(db, o, S.delivered, ctx.user.id, "supplier")
    d = _delivery(db, o)
    d.status, d.delivered_at = DeliveryStatus.delivered, utcnow()
    if notes:
        d.notes = notes
    if proof is not None and proof.filename:
        rec = save_upload(db, proof, FilePurpose.delivery_proof, owner_user_id=ctx.user.id, business_id=ctx.business_id)
        d.proof_file_id = rec.id
    commissions.on_order_event(db, o, "delivered")
    _notify_retailer(db, o, "order_delivered", "retailer.deliveries.confirm")
    _notify_rep(db, o, "order_delivered")
    return _sup_done(db, o, ctx, "deliver", request)


@router.post("/supplier/orders/{oid}/collections", status_code=201)
def record_collection(oid: uuid.UUID, request: Request, amount: Decimal = Form(...), method: str = Form(...),
                      reference: str | None = Form(None), notes: str | None = Form(None), proof: UploadFile | None = File(None),
                      db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.collections.manage"))):
    data = CollectionIn(amount=amount, method=method, reference=reference, notes=notes)
    o = _supplier_order(db, ctx, oid)
    if o.status not in svc.SALES_STATUSES:
        raise Conflict("order_not_collectable")
    if o.paid_amount + data.amount > o.total:
        raise ValidationFailed("collection_exceeds_total")
    proof_id = None
    if proof is not None and proof.filename:
        proof_id = save_upload(db, proof, FilePurpose.payment_proof, owner_user_id=ctx.user.id, business_id=ctx.business_id).id
    with system_context(db):
        db.add(OrderCollection(order_id=o.id, amount=data.amount, method=data.method, reference=data.reference,
                               notes=data.notes, recorded_by=ctx.user.id, proof_file_id=proof_id))
    o.paid_amount = money(o.paid_amount + data.amount)
    o.payment_status = PaymentStatus.paid if o.paid_amount >= o.total else PaymentStatus.partially_paid
    return _sup_done(db, o, ctx, "collection", request, changes=data.model_dump())


@router.post("/supplier/orders/{oid}/invoice")
def upload_invoice(oid: uuid.UUID, request: Request, invoice_number: str = Form(..., max_length=60), file: UploadFile = File(...),
                   db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.manage"))):
    """Attach the supplier's own tax invoice (issued by the supplier's e-invoicing solution)."""
    o = _supplier_order(db, ctx, oid)
    rec = save_upload(db, file, FilePurpose.invoice, owner_user_id=ctx.user.id, business_id=ctx.business_id)
    o.invoice_file_id, o.invoice_number = rec.id, invoice_number
    return _sup_done(db, o, ctx, "invoice_upload", request, changes={"invoice_number": invoice_number})


@router.get("/supplier/orders-summary")
def supplier_summary(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx("supplier.orders.view"))):
    rows = db.execute(select(Order.status, func.count()).where(Order.supplier_id == ctx.business_id).group_by(Order.status)).all()
    return {s.value: n for s, n in rows}


__all__ = ["router", "or_"]
