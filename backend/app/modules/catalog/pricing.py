"""Pricing engine: base offer price → price list override → best active promotion.

Representatives can never alter supplier prices: every order line price is
computed here from supplier-controlled data."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.utils import money, utcnow
from app.models.catalog import PriceList, PriceListItem, PriceRule, SupplierProduct
from app.models.enums import PriceListType, PromotionKind, SaleUnit


@dataclass
class Price:
    list_unit_price: Decimal  # catalog / price-list price for the chosen unit
    discount_per_unit: Decimal
    unit_price: Decimal  # net price for the chosen unit
    pieces_per_unit: int
    promotion_id: uuid.UUID | None
    price_list_id: uuid.UUID | None


def _applies(targets: list, value) -> bool:
    return not targets or (value is not None and str(value) in {str(t) for t in targets})


def active_price_lists(db: Session, supplier_id: uuid.UUID, at: datetime) -> list[PriceList]:
    return list(db.scalars(select(PriceList).where(
        PriceList.supplier_id == supplier_id, PriceList.is_active.is_(True),
        or_(PriceList.valid_from.is_(None), PriceList.valid_from <= at),
        or_(PriceList.valid_to.is_(None), PriceList.valid_to >= at),
    ).order_by(PriceList.priority)))


def active_promotions(db: Session, supplier_id: uuid.UUID, at: datetime) -> list[PriceRule]:
    return list(db.scalars(select(PriceRule).where(
        PriceRule.supplier_id == supplier_id, PriceRule.is_active.is_(True), PriceRule.starts_at <= at, PriceRule.ends_at >= at)))


class PricingContext:
    """Caches price lists & promotions of one supplier for repeated lookups (avoids N+1)."""

    def __init__(self, db: Session, supplier_id: uuid.UUID, retailer_id: uuid.UUID | None, city_id: int | None,
                 at: datetime | None = None):
        self.db = db
        self.retailer_id = retailer_id
        self.city_id = city_id
        self.at = at or utcnow()
        lists = active_price_lists(db, supplier_id, self.at)
        rank = {PriceListType.customer: 0, PriceListType.region: 1, PriceListType.default: 2}
        self.lists = sorted(
            [pl for pl in lists if (
                (pl.type == PriceListType.customer and retailer_id and _applies(pl.customer_business_ids, retailer_id)
                 and pl.customer_business_ids)
                or (pl.type == PriceListType.region and city_id and pl.city_ids and _applies(pl.city_ids, city_id))
                or pl.type == PriceListType.default)],
            key=lambda pl: (rank[pl.type], pl.priority),
        )
        self.items: dict[tuple[uuid.UUID, uuid.UUID], PriceListItem] = {}
        if self.lists:
            ids = [pl.id for pl in self.lists]
            for it in db.scalars(select(PriceListItem).where(PriceListItem.price_list_id.in_(ids))):
                self.items[(it.price_list_id, it.supplier_product_id)] = it
        self.promos = [p for p in active_promotions(db, supplier_id, self.at)
                       if _applies(p.customer_business_ids, retailer_id) and _applies(p.city_ids, city_id)]

    def price(self, sp: SupplierProduct, unit: SaleUnit = SaleUnit.piece, quantity: int = 1) -> Price:
        ppc = max(sp.pieces_per_carton or 1, 1)
        piece_price = Decimal(sp.unit_price)
        carton_price = Decimal(sp.carton_price) if sp.carton_price is not None else piece_price * ppc
        used_list = None
        for pl in self.lists:
            it = self.items.get((pl.id, sp.id))
            if it:
                piece_price = Decimal(it.unit_price)
                carton_price = Decimal(it.carton_price) if it.carton_price is not None else piece_price * ppc
                used_list = pl.id
                break
        pieces_per_unit = ppc if unit == SaleUnit.carton else 1
        list_price = carton_price if unit == SaleUnit.carton else piece_price
        pieces = pieces_per_unit * max(quantity, 1)
        effective_piece = list_price / pieces_per_unit

        best, best_id = Decimal("0"), None
        for rule in self.promos:
            if rule.supplier_product_id and rule.supplier_product_id != sp.id:
                continue
            if rule.category_id and rule.category_id != sp.product.category_id:
                continue
            if pieces < (rule.min_qty or 1):
                continue
            if rule.kind in (PromotionKind.percent, PromotionKind.quantity_tier):
                d_piece = effective_piece * Decimal(rule.value) / Decimal(100)
            else:
                d_piece = min(Decimal(rule.value), effective_piece)
            d_unit = money(d_piece * pieces_per_unit)
            if d_unit > best:
                best, best_id = d_unit, rule.id
        list_price = money(list_price)
        best = min(best, list_price)
        return Price(list_unit_price=list_price, discount_per_unit=best, unit_price=money(list_price - best),
                     pieces_per_unit=pieces_per_unit, promotion_id=best_id, price_list_id=used_list)
