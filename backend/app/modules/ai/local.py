"""Deterministic AI features that work without any external provider.

Every function reads only data the caller is authorized to see (scoped by the
caller's business / representative id) and returns its data sources."""
from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.db import system_context
from app.core.i18n import localized
from app.core.utils import money, normalize_search, utcnow
from app.models.business import Branch, Business, City, CoverageArea
from app.models.catalog import Product, SupplierProduct
from app.models.crm import Customer, Visit
from app.models.enums import (
    Availability,
    BusinessStatus,
    BusinessType,
    CustomerStatus,
    OrderStatus as S,
    SaleUnit,
    VerificationStatus,
    VisitStatus,
)
from app.models.orders import Order, OrderItem
from app.models.reps import RepresentativeArea
from app.modules.orders.service import SALES_STATUSES

AR_NUMBERS = {"واحد": 1, "واحده": 1, "اثنين": 2, "اثنان": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5,
              "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10,
              "عشره": 10, "عشرين": 20, "ثلاثين": 30, "خمسين": 50, "مية": 100, "ميه": 100, "one": 1, "two": 2, "three": 3,
              "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "dozen": 12,
              "درزن": 12, "دزينه": 12}
CARTON_WORDS = {"كرتون", "كراتين", "كرتونه", "كرتونين", "صندوق", "صناديق", "carton", "cartons", "ctn", "ctns", "box", "boxes",
                "case", "cases", "کارٹن", "डिब्बा", "डिब्बे", "कार्टन"}
PIECE_WORDS = {"حبه", "حبات", "قطعه", "قطع", "علبه", "علب", "زجاجه", "زجاجات", "كيس", "اكياس", "piece", "pieces", "pcs", "pc",
               "unit", "units", "bottle", "bottles", "can", "cans", "pack", "packs", "عدد", "پیس", "पीस"}
FILLER = {"من", "ابي", "ابغى", "ابغي", "اريد", "لو", "سمحت", "please", "i", "want", "need", "send", "me", "of", "and", "add",
          "ارسل", "اطلب", "اضف", "و", "مع", "حق", "نوع"}


def _qty_unit(tokens: list[str]) -> tuple[int | None, SaleUnit | None, list[str]]:
    qty, unit, rest = None, None, []
    for tok in tokens:
        if qty is None and re.fullmatch(r"\d{1,5}", tok):
            qty = int(tok)
        elif qty is None and tok in AR_NUMBERS:
            qty = AR_NUMBERS[tok]
        elif tok in CARTON_WORDS or tok.rstrip("ين") in CARTON_WORDS:
            unit = SaleUnit.carton
            if tok == "كرتونين" and qty is None:
                qty = 2
        elif tok in PIECE_WORDS:
            unit = SaleUnit.piece
        elif tok not in FILLER:
            rest.append(tok)
    return qty, unit, rest


def split_lines(text_in: str) -> list[str]:
    out = []
    for chunk in re.split(r"[\n\r,،;؛]+", text_in or ""):
        norm = normalize_search(chunk)
        for part in re.split(r"\s+و\s*(?=\d)|\s+and\s+|\s+\+\s+", norm):
            part = part.strip(" .-")
            if part:
                out.append(part)
    return out


def offer_candidates(db: Session, query: str, offers_stmt, limit: int = 3):
    """Rank offers by trigram similarity to the query (pg_trgm), falling back to ILIKE terms."""
    norm = normalize_search(query)
    if not norm:
        return []
    sim = func.similarity(Product.search_text, norm)
    word_sim = func.word_similarity(norm, Product.search_text)
    stmt = (offers_stmt.add_columns(func.greatest(sim, word_sim).label("score"))
            .where(or_(Product.search_text.op("%")(norm), word_sim > 0.3,
                       *[Product.search_text.ilike(f"%{t}%") for t in norm.split(" ") if len(t) > 2]))
            .order_by(text("score DESC")).limit(limit))
    return [(row[0], float(row[1] or 0)) for row in db.execute(stmt).all()]


def parse_order_text(db: Session, text_in: str, offers_stmt, locale: str) -> dict:
    """Natural language → proposed cart lines. Never places or approves orders."""
    lines = []
    for raw in split_lines(text_in)[:50]:
        qty, unit, rest = _qty_unit(raw.split(" "))
        query = " ".join(rest)
        if not query:
            continue
        cands = offer_candidates(db, query, offers_stmt)
        best = cands[0] if cands else None
        sp = best[0] if best else None
        confidence = round(min(best[1] * 1.4, 1.0), 2) if best else 0
        if sp is not None and unit is None:
            unit = SaleUnit.carton if (sp.sell_by_carton and not sp.sell_by_piece) else SaleUnit.piece
        if sp is not None and unit == SaleUnit.carton and not sp.sell_by_carton:
            unit = SaleUnit.piece
        lines.append({
            "input": raw, "quantity": qty or 1, "quantity_detected": qty is not None, "unit": unit.value if unit else "piece",
            "match": None if sp is None else {"offer_id": str(sp.id), "supplier_id": str(sp.supplier_id),
                                               "product_id": str(sp.product_id),
                                               "name": sp.product.name_ar if locale == "ar" else sp.product.name_en,
                                               "availability": sp.availability.value},
            "confidence": confidence,
            "alternatives": [{"offer_id": str(c.id), "name": c.product.name_ar if locale == "ar" else c.product.name_en,
                              "score": round(s, 2)} for c, s in cands[1:]],
            "needs_review": sp is None or confidence < 0.6 or qty is None,
        })
    return {"lines": lines, "sources": ["catalog:active_offers"],
            "notice": "proposal_only"}  # the user must review and add to cart themselves


def alternatives(db: Session, product_id: uuid.UUID, offers_stmt, locale: str, limit: int = 8) -> dict:
    p = db.get(Product, product_id)
    if p is None:
        return {"items": [], "sources": []}
    stmt = (offers_stmt.where(Product.category_id == p.category_id, Product.id != p.id,
                              SupplierProduct.availability.in_([Availability.in_stock, Availability.low_stock]))
            .add_columns(func.similarity(Product.search_text, p.search_text).label("score"))
            .order_by(text("score DESC")).limit(limit * 2))
    seen, items = set(), []
    for sp, score in db.execute(stmt).all():
        if sp.product_id in seen:
            continue
        seen.add(sp.product_id)
        same_size = bool(p.package_size and sp.product.package_size and
                         normalize_search(p.package_size) == normalize_search(sp.product.package_size))
        items.append({"offer_id": str(sp.id), "product_id": str(sp.product_id), "supplier_id": str(sp.supplier_id),
                      "name": sp.product.name_ar if locale == "ar" else sp.product.name_en, "package_size": sp.product.package_size,
                      "unit_price": sp.unit_price, "same_package_size": same_size, "similarity": round(float(score or 0), 2)})
    items.sort(key=lambda x: (not x["same_package_size"], -x["similarity"]))
    return {"items": items[:limit], "sources": ["catalog:active_offers", f"category:{p.category_id}"]}


def reorder_forecast(db: Session, retailer_id: uuid.UUID, locale: str) -> dict:
    """Predict next purchase date per product from the store's own order history."""
    rows = db.execute(select(OrderItem.product_id, OrderItem.name_ar, OrderItem.name_en, Order.created_at, OrderItem.quantity,
                             OrderItem.pieces_per_unit, Order.supplier_id, OrderItem.supplier_product_id)
                      .join(Order, Order.id == OrderItem.order_id)
                      .where(Order.retailer_id == retailer_id, Order.status.in_(SALES_STATUSES | {S.completed}),
                             Order.created_at >= utcnow() - timedelta(days=180))
                      .order_by(Order.created_at)).all()
    hist: dict = defaultdict(list)
    meta = {}
    for pid, ar, en, at, q, ppu, sup, spid in rows:
        hist[pid].append((at, q * ppu))
        meta[pid] = (ar if locale == "ar" else en, sup, spid)
    now = utcnow()
    out = []
    for pid, events in hist.items():
        dates = sorted({e[0].date() for e in events})
        if len(dates) < 2:
            continue
        gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
        if not gaps:
            continue
        interval = sum(gaps) / len(gaps)
        last = dates[-1]
        nxt = last + timedelta(days=round(interval))
        avg_pieces = sum(e[1] for e in events) / len(events)
        days_left = (nxt - now.date()).days
        out.append({"product_id": str(pid), "name": meta[pid][0], "supplier_id": str(meta[pid][1]), "offer_id": str(meta[pid][2]),
                    "orders": len(dates), "avg_interval_days": round(interval, 1), "last_order": last.isoformat(),
                    "predicted_next": nxt.isoformat(), "days_until": days_left, "suggested_pieces": round(avg_pieces),
                    "urgency": "due" if days_left <= 2 else ("soon" if days_left <= 7 else "later")})
    out.sort(key=lambda x: x["days_until"])
    return {"items": out[:50], "sources": ["orders:your_store:last_180_days"],
            "method": "average interval between past purchase dates"}


def rep_opportunities(db: Session, rep_id: uuid.UUID, locale: str) -> dict:
    now = utcnow()
    cities = [a.city_id for a in db.scalars(select(RepresentativeArea).where(RepresentativeArea.representative_id == rep_id))]
    scored = []
    for c in db.scalars(select(Customer).where(Customer.owner_representative_id == rep_id)):
        score, reasons = 0, []
        if c.status == CustomerStatus.active and c.last_order_at and c.last_order_at < now - timedelta(days=21):
            score += 40
            reasons.append("lapsed_customer")
        if c.next_follow_up_at and c.next_follow_up_at <= now + timedelta(days=1):
            score += 30
            reasons.append("follow_up_due")
        if c.status in (CustomerStatus.lead, CustomerStatus.prospect) and (not c.last_visit_at or c.last_visit_at < now - timedelta(days=14)):
            score += 20
            reasons.append("unconverted_lead")
        if c.orders_count and c.total_sales:
            score += min(int(Decimal(c.total_sales) / 500), 20)
        if score:
            scored.append({"customer_id": str(c.id), "name": c.name, "score": score, "reasons": reasons,
                           "last_order_at": c.last_order_at, "next_follow_up_at": c.next_follow_up_at})
    known = set(db.scalars(select(Customer.retailer_id).where(Customer.owner_representative_id == rep_id, Customer.retailer_id.isnot(None))))
    new_stores = []
    if cities:
        with system_context(db):
            for br, biz in db.execute(select(Branch, Business).join(Business, Business.id == Branch.business_id).where(
                    Business.type == BusinessType.retailer, Business.discoverable.is_(True), Business.status == BusinessStatus.active,
                    Branch.city_id.in_(cities), Branch.is_active.is_(True)).order_by(Business.created_at.desc()).limit(40)).all():
                if biz.id not in known:
                    new_stores.append({"retailer_id": str(biz.id), "name": biz.trade_name_ar, "district": br.district,
                                       "city_id": br.city_id, "reason": "new_store_in_your_area"})
    scored.sort(key=lambda x: -x["score"])
    return {"customers": scored[:30], "new_stores": new_stores[:20],
            "sources": ["crm:your_customers", "directory:discoverable_stores_in_your_areas"]}


def rep_performance(db: Session, rep_id: uuid.UUID, days: int = 30) -> dict:
    now = utcnow()
    start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)

    def window(a, b):
        created = db.scalar(select(func.count()).select_from(Order).where(Order.representative_id == rep_id, Order.created_at.between(a, b))) or 0
        won = db.scalar(select(func.count()).select_from(Order).where(Order.representative_id == rep_id, Order.created_at.between(a, b),
                                                                      Order.status.in_(SALES_STATUSES | {S.completed}))) or 0
        sales = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.representative_id == rep_id, Order.created_at.between(a, b),
                                                                                 Order.status.in_(SALES_STATUSES | {S.completed}))) or 0
        visits = db.scalar(select(func.count()).select_from(Visit).where(Visit.representative_id == rep_id, Visit.status == VisitStatus.completed,
                                                                         Visit.ended_at.between(a, b))) or 0
        rejected = db.scalar(select(func.count()).select_from(Order).where(Order.representative_id == rep_id, Order.created_at.between(a, b),
                                                                           Order.status == S.rejected)) or 0
        return {"orders_created": created, "orders_won": won, "sales": money(sales), "visits": visits, "rejected": rejected,
                "conversion": round(won / created * 100, 1) if created else 0,
                "orders_per_visit": round(created / visits, 2) if visits else 0}

    cur, prev = window(start, now), window(prev_start, start)
    insights = []
    if cur["sales"] > prev["sales"]:
        insights.append({"code": "sales_up", "value": str(cur["sales"] - prev["sales"])})
    elif cur["sales"] < prev["sales"]:
        insights.append({"code": "sales_down", "value": str(prev["sales"] - cur["sales"])})
    if cur["orders_created"] and cur["conversion"] < 60:
        insights.append({"code": "low_conversion", "value": cur["conversion"]})
    if cur["visits"] and cur["orders_per_visit"] < 0.3:
        insights.append({"code": "few_orders_per_visit", "value": cur["orders_per_visit"]})
    if cur["rejected"]:
        insights.append({"code": "rejections", "value": cur["rejected"]})
    return {"current": cur, "previous": prev, "days": days, "insights": insights,
            "sources": ["orders:your_orders", "visits:your_visits"]}


def coverage_gaps(db: Session, supplier_id: uuid.UUID | None, locale: str) -> dict:
    """Cities with many registered stores but little supply coverage (or not covered by this supplier)."""
    with system_context(db):
        stores = dict(db.execute(select(Branch.city_id, func.count(func.distinct(Branch.business_id))).join(
            Business, Business.id == Branch.business_id).where(Business.type == BusinessType.retailer, Branch.city_id.isnot(None))
            .group_by(Branch.city_id)).all())
        suppliers = dict(db.execute(select(CoverageArea.city_id, func.count(func.distinct(CoverageArea.supplier_id))).join(
            Business, Business.id == CoverageArea.supplier_id).where(
            Business.verification_status == VerificationStatus.verified, CoverageArea.is_active.is_(True))
            .group_by(CoverageArea.city_id)).all())
        reps = dict(db.execute(select(RepresentativeArea.city_id, func.count(func.distinct(RepresentativeArea.representative_id)))
                               .group_by(RepresentativeArea.city_id)).all())
        mine = set(db.scalars(select(CoverageArea.city_id).where(CoverageArea.supplier_id == supplier_id))) if supplier_id else set()
        cities = {c.id: c for c in db.scalars(select(City))}
    out = []
    for cid, n_stores in stores.items():
        n_sup, n_rep = suppliers.get(cid, 0), reps.get(cid, 0)
        ratio = n_stores / max(n_sup, 1)
        out.append({"city_id": cid, "city": localized(cities[cid].name, locale) if cid in cities else str(cid), "stores": n_stores,
                    "suppliers": n_sup, "representatives": n_rep, "stores_per_supplier": round(ratio, 1),
                    "you_cover": cid in mine if supplier_id else None,
                    "opportunity": (not supplier_id or cid not in mine) and (ratio >= 3 or n_rep == 0)})
    out.sort(key=lambda x: (not x["opportunity"], -x["stores_per_supplier"]))
    return {"items": out, "sources": ["directory:registered_store_branches (counts only)", "coverage:verified_suppliers",
                                      "representatives:work_areas"]}


def supplier_summary(report: dict, locale: str) -> dict:
    """Template-based narrative over the supplier's own report numbers."""
    k = report["kpis"]
    bullets = [{"code": "sales_total", "params": {"sales": str(k["sales"]), "orders": k["orders"]}},
               {"code": "avg_order", "params": {"avg": str(k["avg_order"])}},
               {"code": "customers", "params": {"active": k["active_customers"], "new": k["new_customers"]}}]
    if report["top_products"]:
        tp = report["top_products"][0]
        bullets.append({"code": "top_product", "params": {"name": tp["name"], "value": str(tp["value"])}})
    if report["representatives"]:
        r = report["representatives"][0]
        bullets.append({"code": "top_rep", "params": {"name": r["name"], "value": str(r["value"])}})
    if k["returns"]:
        bullets.append({"code": "returns", "params": {"count": k["returns"], "value": str(k["returns_value"])}})
    if k["new_orders"]:
        bullets.append({"code": "pending_new", "params": {"count": k["new_orders"]}})
    return {"bullets": bullets, "sources": [f"report:supplier:{report['period']['from']}..{report['period']['to']}"]}


__all__ = ["parse_order_text", "alternatives", "reorder_forecast", "rep_opportunities", "rep_performance", "coverage_gaps",
           "supplier_summary", "offer_candidates", "and_"]
