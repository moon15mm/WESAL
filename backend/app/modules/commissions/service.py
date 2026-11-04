"""Commission engine.

Rule selection per order line: the most specific matching rule wins
(product > brand > category > all), then the lowest priority number.
- percent:          line_net × rate / 100
- per_unit:         pieces × rate (pieces = quantity × pieces per sale unit)
- fixed_per_order:  rate once per order (largest matching fixed rule)

Lifecycle: estimated (order approved) → pending (delivered) → due (completed +
hold period, scheduler) → approved (supplier) → paid (payout recorded).
Cancellation/rejection → cancelled. Returns create commission_adjustments
(unique per return) so a single event can never adjust twice; one commission per
(order, representative) is enforced by a unique index."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import system_context
from app.core.utils import money, utcnow
from app.models.commissions import Commission, CommissionAdjustment
from app.models.enums import CommissionBasis, CommissionScope, CommissionStatus as CS
from app.models.orders import Order
from app.models.reps import Authorization, CommissionAgreement, CommissionRule, Representative
from app.modules.notifications.service import notify

SPECIFICITY = {CommissionScope.product: 0, CommissionScope.brand: 1, CommissionScope.category: 2, CommissionScope.all: 3}


def _matches(rule: CommissionRule, item) -> bool:
    if rule.scope == CommissionScope.all:
        return True
    if rule.scope == CommissionScope.product:
        return rule.product_id == item.product_id
    if rule.scope == CommissionScope.brand:
        return rule.brand_id is not None and rule.brand_id == item.brand_id
    if rule.scope == CommissionScope.category:
        return rule.category_id == item.category_id
    return False


def calculate(agreement: CommissionAgreement, order: Order, use_delivered: bool = False,
              returned: dict | None = None) -> tuple[Decimal, Decimal, list[dict]]:
    returned = returned or {}
    order_value = order.subtotal - order.discount_total
    rules = [r for r in agreement.rules if r.min_order_value is None or order_value >= r.min_order_value]
    line_rules = [r for r in rules if r.basis != CommissionBasis.fixed_per_order]
    fixed_rules = [r for r in rules if r.basis == CommissionBasis.fixed_per_order]
    total, eligible, breakdown = Decimal("0"), Decimal("0"), []
    any_eligible = False
    for item in order.items:
        qty = item.quantity
        if use_delivered and item.delivered_qty is not None:
            qty = item.delivered_qty
        qty = max(qty - returned.get(item.id, item.returned_qty or 0), 0)
        if qty <= 0:
            continue
        unit_net = (item.line_total / item.quantity) if item.quantity else Decimal("0")
        line_net = money(unit_net * qty)
        matching = sorted([r for r in line_rules if _matches(r, item)], key=lambda r: (SPECIFICITY[r.scope], r.priority))
        fixed_match = any(_matches(r, item) for r in fixed_rules)
        if not matching:
            if fixed_match:
                any_eligible = True
                eligible += line_net
            continue
        rule = matching[0]
        if rule.basis == CommissionBasis.percent:
            amount = money(line_net * Decimal(rule.rate) / Decimal(100))
        else:  # per_unit
            amount = money(Decimal(rule.rate) * qty * item.pieces_per_unit)
        any_eligible = True
        eligible += line_net
        total += amount
        breakdown.append({"order_item_id": str(item.id), "rule_id": str(rule.id), "basis": rule.basis.value,
                          "rate": str(rule.rate), "quantity": qty, "base": str(line_net), "amount": str(amount)})
    if fixed_rules and any_eligible:
        best = max(fixed_rules, key=lambda r: r.rate)
        total += money(best.rate)
        breakdown.append({"rule_id": str(best.id), "basis": best.basis.value, "rate": str(best.rate), "amount": str(money(best.rate))})
    return money(total), money(eligible), breakdown


def _get(db: Session, order: Order) -> Commission | None:
    return db.scalar(select(Commission).where(Commission.order_id == order.id, Commission.representative_id == order.representative_id))


def _notify_rep(db: Session, c: Commission, order: Order) -> None:
    rep = db.get(Representative, c.representative_id)
    if rep:
        notify(db, [rep.user_id], "commission_updated", {"number": order.number, "amount": str(c.amount), "status": c.status.value},
               link="/app/rep/commissions", entity_type="commission", entity_id=c.id,
               dedupe_key=f"commission:{c.id}:{c.status.value}:{c.amount}")


def on_order_event(db: Session, order: Order, event: str) -> Commission | None:
    """event: approved | delivered | completed | cancelled | return:<id> | disputed | dispute_resolved"""
    if not order.representative_id or not order.authorization_id:
        return None
    with system_context(db):
        auth = db.get(Authorization, order.authorization_id)
        agreement = db.get(CommissionAgreement, auth.agreement_id) if auth and auth.agreement_id else None
        c = _get(db, order)
        if agreement is None:
            return None
        if event == "approved":
            amount, eligible, breakdown = calculate(agreement, order)
            if c is None:
                c = Commission(order_id=order.id, supplier_id=order.supplier_id, representative_id=order.representative_id,
                               authorization_id=auth.id, agreement_id=agreement.id, status=CS.estimated, amount=amount,
                               original_amount=amount, eligible_amount=eligible, breakdown=breakdown, currency=order.currency)
                db.add(c)
                db.flush()
            elif c.status in (CS.estimated, CS.pending):
                c.amount = c.original_amount = amount
                c.eligible_amount, c.breakdown = eligible, breakdown
        elif c is None:
            return None
        elif event == "delivered" and c.status == CS.estimated:
            c.status = CS.pending
        elif event == "completed" and c.status in (CS.estimated, CS.pending):
            amount, eligible, breakdown = calculate(agreement, order, use_delivered=True)
            c.amount, c.eligible_amount, c.breakdown = amount, eligible, breakdown
            c.status = CS.pending
            c.due_at = utcnow() + timedelta(days=agreement.hold_days)
            if agreement.hold_days == 0:
                c.status = CS.due
        elif event == "cancelled" and c.status not in (CS.paid, CS.cancelled):
            c.status = CS.cancelled
            c.status_reason = "order cancelled"
        elif event == "disputed" and c.status in (CS.estimated, CS.pending, CS.due, CS.approved):
            c.status_reason = "order disputed"
            c.status = CS.disputed
        elif event.startswith("return:"):
            return_id = event.split(":", 1)[1]
            amount, eligible, breakdown = calculate(agreement, order, use_delivered=True)
            delta = money(amount - c.amount)
            if delta != 0:
                exists = db.scalar(select(CommissionAdjustment.id).where(CommissionAdjustment.commission_id == c.id,
                                                                         CommissionAdjustment.reason == "return",
                                                                         CommissionAdjustment.reference_id == return_id))
                if not exists:
                    db.add(CommissionAdjustment(commission_id=c.id, amount_delta=delta, reason="return", reference_id=return_id,
                                                note=f"return on order {order.number}"))
                    c.amount = max(amount, Decimal("0"))
                    c.eligible_amount, c.breakdown = eligible, breakdown
                    if c.status == CS.paid:
                        c.status = CS.adjusted  # paid already: clawback settled off-platform
                    if c.amount == 0 and c.status not in (CS.paid, CS.adjusted):
                        c.status = CS.cancelled
                        c.status_reason = "fully returned"
        else:
            return c
        _notify_rep(db, c, order)
        return c


def release_due(db: Session) -> int:
    """Scheduler: pending commissions past their hold period become due."""
    now = utcnow()
    n = 0
    for c in db.scalars(select(Commission).where(Commission.status == CS.pending, Commission.due_at.isnot(None),
                                                 Commission.due_at <= now)):
        c.status = CS.due
        n += 1
    return n
