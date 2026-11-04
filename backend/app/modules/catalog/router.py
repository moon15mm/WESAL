"""Catalog: supplier product offers, brands, price lists, promotions, and the marketplace."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, system_context
from app.core.deps import BusinessCtx, Principal, current_principal, supplier_ctx
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.i18n import localized
from app.core.schemas import PageParams, paginate
from app.core.storage import save_upload
from app.core.utils import normalize_search, slugify, utcnow
from app.models.business import Branch, Business, CoverageArea
from app.models.catalog import Brand, Category, PriceList, PriceListItem, PriceRule, Product, ProductUnit, SupplierProduct
from app.models.enums import (
    Availability,
    BusinessStatus,
    BusinessType,
    FilePurpose,
    PriceListType,
    ProductStatus,
    PromotionKind,
    SaleUnit,
    VerificationStatus,
)
from app.modules.catalog.pricing import PricingContext
from app.modules.common import business_brief, city_out, file_url, product_name

router = APIRouter(tags=["catalog"])


# ------------------------------------------------------------------ helpers
def build_search_text(p: Product, brand: Brand | None = None, extra: str = "") -> str:
    parts = [p.name_ar, p.name_en, *(p.name_i18n or {}).values(), p.barcode or "", p.package_size or "", p.base_sku or "",
             p.manufacturer or "", extra]
    if brand:
        parts += [brand.name_ar, brand.name_en]
    return normalize_search(" ".join(x for x in parts if x))


def apply_search(stmt, q: str | None):
    if not q:
        return stmt
    norm = normalize_search(q)
    terms = [t for t in norm.split(" ") if t][:6]
    if not terms:
        return stmt
    conds = [Product.search_text.ilike(f"%{t.replace('%', '').replace('_', '')}%") for t in terms]
    return stmt.where(or_(and_(*conds), Product.barcode == q.strip()))


def product_out(p: Product, locale: str) -> dict:
    return {
        "id": str(p.id), "name": product_name(p, locale), "name_ar": p.name_ar, "name_en": p.name_en,
        "name_i18n": p.name_i18n or {}, "description": p.description_ar if locale == "ar" else (p.description_en or p.description_ar),
        "description_ar": p.description_ar, "description_en": p.description_en,
        "brand": {"id": str(p.brand.id), "name": p.brand.name_ar if locale == "ar" else p.brand.name_en} if p.brand else None,
        "category": {"id": p.category.id, "name": localized(p.category.name, locale), "slug": p.category.slug},
        "manufacturer": p.manufacturer, "barcode": p.barcode, "base_sku": p.base_sku, "package_size": p.package_size,
        "pieces_per_carton": p.pieces_per_carton, "image_url": file_url(p.image_file_id), "status": p.status.value,
        "updated_at": p.updated_at,
    }


def offer_out(sp: SupplierProduct, locale: str, price_ctx: PricingContext | None = None, supplier: Business | None = None) -> dict:
    out = {
        "id": str(sp.id), "supplier_id": str(sp.supplier_id), "product": product_out(sp.product, locale), "sku": sp.sku,
        "unit_price": sp.unit_price, "carton_price": sp.carton_price, "pieces_per_carton": sp.pieces_per_carton,
        "sell_by_piece": sp.sell_by_piece, "sell_by_carton": sp.sell_by_carton, "min_order_qty": sp.min_order_qty,
        "availability": sp.availability.value, "stock_qty": sp.stock_qty, "is_active": sp.is_active,
        "price_updated_at": sp.price_updated_at, "updated_at": sp.updated_at,
    }
    if price_ctx is not None:
        piece = price_ctx.price(sp, SaleUnit.piece, 1)
        carton = price_ctx.price(sp, SaleUnit.carton, 1)
        out["price"] = {"piece": {"list": piece.list_unit_price, "net": piece.unit_price, "promotion_id": str(piece.promotion_id) if piece.promotion_id else None},
                        "carton": {"list": carton.list_unit_price, "net": carton.unit_price, "promotion_id": str(carton.promotion_id) if carton.promotion_id else None}}
    if supplier is not None:
        out["supplier"] = business_brief(supplier, locale)
    return out


def _check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise ValidationFailed("invalid_category", fields={"category_id": "invalid"})


def _check_brand(db: Session, brand_id: uuid.UUID | None) -> Brand | None:
    if brand_id is None:
        return None
    b = db.get(Brand, brand_id)
    if b is None:
        raise ValidationFailed("invalid_brand", fields={"brand_id": "invalid"})
    return b


# ------------------------------------------------------------------ brands
class BrandIn(BaseModel):
    name_ar: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    manufacturer: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")


@router.get("/catalog/brands")
def list_brands(q: str | None = None, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    stmt = select(Brand).where(Brand.is_active.is_(True)).order_by(Brand.name_en).limit(200)
    if q:
        stmt = stmt.where(or_(Brand.name_ar.ilike(f"%{q}%"), Brand.name_en.ilike(f"%{q}%")))
    return [{"id": str(b.id), "name_ar": b.name_ar, "name_en": b.name_en, "manufacturer": b.manufacturer,
             "logo_url": file_url(b.logo_file_id)} for b in db.scalars(stmt)]


@router.post("/supplier/brands", status_code=201)
def create_brand(data: BrandIn, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.catalog.manage"))):
    existing = db.scalar(select(Brand).where(or_(func.lower(Brand.name_en) == data.name_en.lower(), Brand.name_ar == data.name_ar)))
    if existing:
        return {"id": str(existing.id), "existing": True}
    slug = slugify(data.name_en)
    if db.scalar(select(Brand.id).where(Brand.slug == slug)):
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"
    b = Brand(**data.model_dump(), slug=slug, created_by_business_id=ctx.business_id)
    db.add(b)
    audit(db, "brand.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="brand",
          entity_id=b.id, changes=data.model_dump(), request=request)
    db.commit()
    return {"id": str(b.id), "existing": False}


# ------------------------------------------------------------------ supplier offers
class OfferFields(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    unit_price: Decimal = Field(ge=0, le=1_000_000, decimal_places=2)
    carton_price: Decimal | None = Field(default=None, ge=0, le=10_000_000, decimal_places=2)
    pieces_per_carton: int = Field(default=1, ge=1, le=10000)
    sell_by_piece: bool = True
    sell_by_carton: bool = True
    min_order_qty: int = Field(default=1, ge=1, le=100000)
    availability: Availability = Availability.in_stock
    stock_qty: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _units(self):
        if not (self.sell_by_piece or self.sell_by_carton):
            raise ValueError("at least one sale unit")
        return self


class ProductFields(BaseModel):
    name_ar: str = Field(min_length=2, max_length=255)
    name_en: str = Field(min_length=2, max_length=255)
    name_ur: str | None = Field(default=None, max_length=255)
    name_hi: str | None = Field(default=None, max_length=255)
    description_ar: str | None = Field(default=None, max_length=4000)
    description_en: str | None = Field(default=None, max_length=4000)
    brand_id: uuid.UUID | None = None
    category_id: int
    manufacturer: str | None = Field(default=None, max_length=200)
    barcode: str | None = Field(default=None, pattern=r"^\d{8,14}$")
    package_size: str | None = Field(default=None, max_length=40)


class OfferCreateIn(OfferFields):
    product_id: uuid.UUID | None = None
    product: ProductFields | None = None

    @model_validator(mode="after")
    def _one(self):
        if (self.product_id is None) == (self.product is None):
            raise ValueError("provide product_id or product")
        return self


class OfferUpdateIn(BaseModel):
    sku: str | None = Field(default=None, max_length=64)
    unit_price: Decimal | None = Field(default=None, ge=0, le=1_000_000)
    carton_price: Decimal | None = Field(default=None, ge=0, le=10_000_000)
    pieces_per_carton: int | None = Field(default=None, ge=1, le=10000)
    sell_by_piece: bool | None = None
    sell_by_carton: bool | None = None
    min_order_qty: int | None = Field(default=None, ge=1, le=100000)
    availability: Availability | None = None
    stock_qty: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    product: ProductFields | None = None


def _create_product(db: Session, ctx: BusinessCtx, pf: ProductFields, ppc: int) -> Product:
    _check_category(db, pf.category_id)
    brand = _check_brand(db, pf.brand_id)
    if pf.barcode:
        existing = db.scalar(select(Product).where(Product.barcode == pf.barcode))
        if existing:
            return existing  # same barcode = same product identity; never duplicate
    p = Product(name_ar=pf.name_ar, name_en=pf.name_en,
                name_i18n={k: v for k, v in {"ur": pf.name_ur, "hi": pf.name_hi}.items() if v},
                description_ar=pf.description_ar, description_en=pf.description_en, brand_id=pf.brand_id,
                category_id=pf.category_id, manufacturer=pf.manufacturer or (brand.manufacturer if brand else None),
                barcode=pf.barcode, package_size=pf.package_size, pieces_per_carton=ppc, status=ProductStatus.active,
                created_by_business_id=ctx.business_id)
    p.search_text = build_search_text(p, brand)
    db.add(p)
    db.flush()
    db.add(ProductUnit(product_id=p.id, unit=SaleUnit.piece, pieces=1))
    if ppc > 1:
        db.add(ProductUnit(product_id=p.id, unit=SaleUnit.carton, pieces=ppc))
    return p


@router.get("/supplier/products")
def my_offers(q: str | None = None, category_id: int | None = None, availability: Availability | None = None,
              active: bool | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
              ctx: BusinessCtx = Depends(supplier_ctx())):
    stmt = select(SupplierProduct).join(Product, Product.id == SupplierProduct.product_id).where(
        SupplierProduct.supplier_id == ctx.business_id).order_by(Product.name_en)
    stmt = apply_search(stmt, q)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if availability:
        stmt = stmt.where(SupplierProduct.availability == availability)
    if active is not None:
        stmt = stmt.where(SupplierProduct.is_active.is_(active))
    return paginate(db, stmt, params, lambda sp: offer_out(sp, ctx.principal.locale))


@router.post("/supplier/products", status_code=201)
def create_offer(data: OfferCreateIn, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx("supplier.catalog.manage"))):
    if data.product_id:
        product = db.get(Product, data.product_id)
        if product is None or product.status != ProductStatus.active:
            raise ValidationFailed("invalid_product")
    else:
        product = _create_product(db, ctx, data.product, data.pieces_per_carton)
    if db.scalar(select(SupplierProduct.id).where(SupplierProduct.supplier_id == ctx.business_id,
                                                  SupplierProduct.product_id == product.id)):
        raise Conflict("offer_exists")
    values = data.model_dump(exclude={"product_id", "product"})
    sp = SupplierProduct(supplier_id=ctx.business_id, product_id=product.id, price_updated_at=utcnow(), **values)
    db.add(sp)
    db.flush()
    audit(db, "offer.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="supplier_product",
          entity_id=sp.id, changes=values, request=request)
    db.commit()
    db.refresh(sp)
    return offer_out(sp, ctx.principal.locale)


@router.get("/supplier/products/{offer_id}")
def get_offer(offer_id: uuid.UUID, db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    sp = db.get(SupplierProduct, offer_id)
    if sp is None or sp.supplier_id != ctx.business_id:
        raise NotFound()
    return offer_out(sp, ctx.principal.locale)


@router.patch("/supplier/products/{offer_id}")
def update_offer(offer_id: uuid.UUID, data: OfferUpdateIn, request: Request, db: Session = Depends(get_db),
                 ctx: BusinessCtx = Depends(supplier_ctx())):
    sp = db.get(SupplierProduct, offer_id)
    if sp is None or sp.supplier_id != ctx.business_id:
        raise NotFound()
    changes = data.model_dump(exclude_unset=True, exclude={"product"})
    price_fields = {"unit_price", "carton_price", "pieces_per_carton"}
    stock_fields = {"availability", "stock_qty", "low_stock_threshold"}
    keys = set(changes)
    if keys & price_fields:
        ctx.require("supplier.pricing.manage")
    if keys & stock_fields and not (ctx.has("supplier.inventory.manage") or ctx.has("supplier.catalog.manage")):
        ctx.require("supplier.inventory.manage")
    if keys - price_fields - stock_fields:
        ctx.require("supplier.catalog.manage")
    old = {k: getattr(sp, k) for k in changes}
    for k, v in changes.items():
        setattr(sp, k, v)
    if not (sp.sell_by_piece or sp.sell_by_carton):
        raise ValidationFailed("sale_unit_required")
    if set(changes) & price_fields:
        sp.price_updated_at = utcnow()
    if data.product is not None:
        ctx.require("supplier.catalog.manage")
        p = sp.product
        if p.created_by_business_id != ctx.business_id:
            raise Forbidden("product_identity_locked")
        pf = data.product
        _check_category(db, pf.category_id)
        brand = _check_brand(db, pf.brand_id)
        if pf.barcode and pf.barcode != p.barcode and db.scalar(select(Product.id).where(Product.barcode == pf.barcode)):
            raise Conflict("barcode_exists")
        for k in ("name_ar", "name_en", "description_ar", "description_en", "brand_id", "category_id", "manufacturer",
                  "barcode", "package_size"):
            setattr(p, k, getattr(pf, k))
        p.name_i18n = {k: v for k, v in {"ur": pf.name_ur, "hi": pf.name_hi}.items() if v}
        p.search_text = build_search_text(p, brand)
    audit(db, "offer.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="supplier_product",
          entity_id=sp.id, changes={"old": old, "new": changes}, request=request)
    db.commit()
    db.refresh(sp)
    return offer_out(sp, ctx.principal.locale)


class StockIn(BaseModel):
    offer_id: uuid.UUID
    availability: Availability
    stock_qty: int | None = Field(default=None, ge=0)


@router.post("/supplier/products/stock")
def bulk_stock(data: list[StockIn], request: Request, db: Session = Depends(get_db),
               ctx: BusinessCtx = Depends(supplier_ctx())):
    if not (ctx.has("supplier.inventory.manage") or ctx.has("supplier.catalog.manage")):
        ctx.require("supplier.inventory.manage")
    if len(data) > 1000:
        raise ValidationFailed("too_many_items")
    ids = [d.offer_id for d in data]
    offers = {sp.id: sp for sp in db.scalars(select(SupplierProduct).where(SupplierProduct.id.in_(ids),
                                                                           SupplierProduct.supplier_id == ctx.business_id))}
    for d in data:
        sp = offers.get(d.offer_id)
        if sp is None:
            raise NotFound(params={"id": str(d.offer_id)})
        sp.availability = d.availability
        sp.stock_qty = d.stock_qty
    audit(db, "offer.stock_bulk", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, changes={"count": len(data)},
          request=request)
    db.commit()
    return {"updated": len(data)}


@router.post("/supplier/products/{offer_id}/image")
def upload_product_image(offer_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db),
                         ctx: BusinessCtx = Depends(supplier_ctx("supplier.catalog.manage"))):
    sp = db.get(SupplierProduct, offer_id)
    if sp is None or sp.supplier_id != ctx.business_id:
        raise NotFound()
    p = sp.product
    if p.created_by_business_id != ctx.business_id and p.image_file_id:
        raise Forbidden("product_identity_locked")
    rec = save_upload(db, file, FilePurpose.product_image, owner_user_id=ctx.user.id, business_id=ctx.business_id)
    p.image_file_id = rec.id
    db.commit()
    return {"image_url": file_url(rec.id)}


IMPORT_COLUMNS = ["name_ar", "name_en", "category_slug", "brand_en", "barcode", "package_size", "pieces_per_carton",
                  "sku", "unit_price", "carton_price", "min_order_qty", "availability"]


@router.post("/supplier/products/import")
def import_offers(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db),
                  ctx: BusinessCtx = Depends(supplier_ctx("supplier.catalog.manage"))):
    """CSV import (UTF-8, header row). Creates/updates offers; rows with errors are reported, not applied."""
    raw = file.file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValidationFailed("file_too_large", params={"max_mb": 5})
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("csv_encoding")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in ("name_ar", "name_en", "category_slug", "unit_price") if c not in (reader.fieldnames or [])]
    if missing:
        raise ValidationFailed("csv_missing_columns", params={"columns": ",".join(missing)})
    cats = {c.slug: c.id for c in db.scalars(select(Category))}
    created = updated = 0
    errors = []
    for i, row in enumerate(reader, start=2):
        if i > 5001:
            errors.append({"row": i, "error": "row_limit"})
            break
        try:
            cat_id = cats.get((row.get("category_slug") or "").strip())
            if not cat_id:
                raise ValueError("invalid_category")
            brand_id = None
            if row.get("brand_en"):
                brand = db.scalar(select(Brand).where(func.lower(Brand.name_en) == row["brand_en"].strip().lower()))
                brand_id = brand.id if brand else None
            ppc = int(row.get("pieces_per_carton") or 1)
            pf = ProductFields(name_ar=row["name_ar"].strip(), name_en=row["name_en"].strip(), category_id=cat_id,
                               brand_id=brand_id, barcode=(row.get("barcode") or "").strip() or None,
                               package_size=(row.get("package_size") or "").strip() or None)
            offer = OfferFields(sku=(row.get("sku") or "").strip() or None, unit_price=Decimal(row["unit_price"]),
                                carton_price=Decimal(row["carton_price"]) if row.get("carton_price") else None,
                                pieces_per_carton=ppc, min_order_qty=int(row.get("min_order_qty") or 1),
                                availability=Availability(row.get("availability") or "in_stock"))
            with db.begin_nested():
                product = _create_product(db, ctx, pf, ppc)
                sp = db.scalar(select(SupplierProduct).where(SupplierProduct.supplier_id == ctx.business_id,
                                                             SupplierProduct.product_id == product.id))
                if sp:
                    for k, v in offer.model_dump().items():
                        setattr(sp, k, v)
                    sp.price_updated_at = utcnow()
                    updated += 1
                else:
                    db.add(SupplierProduct(supplier_id=ctx.business_id, product_id=product.id, price_updated_at=utcnow(),
                                           **offer.model_dump()))
                    created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"row": i, "error": str(exc)[:200]})
    audit(db, "offer.import", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id,
          changes={"created": created, "updated": updated, "errors": len(errors)}, request=request)
    db.commit()
    return {"created": created, "updated": updated, "errors": errors[:200], "columns": IMPORT_COLUMNS}


# ------------------------------------------------------------------ price lists
class PriceListItemIn(BaseModel):
    offer_id: uuid.UUID
    unit_price: Decimal = Field(ge=0, le=1_000_000)
    carton_price: Decimal | None = Field(default=None, ge=0)


class PriceListIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    type: PriceListType
    priority: int = Field(default=100, ge=1, le=1000)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool = True
    customer_business_ids: list[uuid.UUID] = []
    city_ids: list[int] = []
    items: list[PriceListItemIn] = []

    @model_validator(mode="after")
    def _targets(self):
        if self.type == PriceListType.customer and not self.customer_business_ids:
            raise ValueError("customer price list requires customers")
        if self.type == PriceListType.region and not self.city_ids:
            raise ValueError("region price list requires cities")
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("invalid validity window")
        return self


def price_list_out(pl: PriceList) -> dict:
    return {"id": str(pl.id), "name": pl.name, "type": pl.type.value, "priority": pl.priority, "valid_from": pl.valid_from,
            "valid_to": pl.valid_to, "is_active": pl.is_active, "customer_business_ids": pl.customer_business_ids,
            "city_ids": pl.city_ids, "items": [{"offer_id": str(i.supplier_product_id), "unit_price": i.unit_price,
                                                "carton_price": i.carton_price} for i in pl.items]}


def _save_price_list(db: Session, ctx: BusinessCtx, pl: PriceList, data: PriceListIn) -> None:
    offer_ids = {i.offer_id for i in data.items}
    if len(offer_ids) != len(data.items):
        raise ValidationFailed("duplicate_items")
    if offer_ids:
        owned = set(db.scalars(select(SupplierProduct.id).where(SupplierProduct.id.in_(offer_ids),
                                                                SupplierProduct.supplier_id == ctx.business_id)))
        if owned != offer_ids:
            raise ValidationFailed("invalid_offer")
    if data.customer_business_ids:
        n = db.scalar(select(func.count()).select_from(Business).where(Business.id.in_(data.customer_business_ids),
                                                                         Business.type == BusinessType.retailer))
        if n != len(set(data.customer_business_ids)):
            raise ValidationFailed("invalid_customer")
    pl.name, pl.type, pl.priority = data.name, data.type, data.priority
    pl.valid_from, pl.valid_to, pl.is_active = data.valid_from, data.valid_to, data.is_active
    pl.customer_business_ids = [str(x) for x in data.customer_business_ids]
    pl.city_ids = data.city_ids
    pl.items.clear()
    db.flush()
    for it in data.items:
        pl.items.append(PriceListItem(supplier_product_id=it.offer_id, unit_price=it.unit_price, carton_price=it.carton_price))


@router.get("/supplier/price-lists")
def list_price_lists(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(PriceList).where(PriceList.supplier_id == ctx.business_id).order_by(PriceList.priority)).all()
    return [price_list_out(pl) for pl in rows]


@router.post("/supplier/price-lists", status_code=201)
def create_price_list(data: PriceListIn, request: Request, db: Session = Depends(get_db),
                      ctx: BusinessCtx = Depends(supplier_ctx("supplier.pricing.manage"))):
    pl = PriceList(supplier_id=ctx.business_id, name=data.name, type=data.type)
    db.add(pl)
    db.flush()
    _save_price_list(db, ctx, pl, data)
    audit(db, "price_list.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="price_list",
          entity_id=pl.id, changes=data.model_dump(), request=request)
    db.commit()
    return price_list_out(pl)


@router.put("/supplier/price-lists/{pl_id}")
def update_price_list(pl_id: uuid.UUID, data: PriceListIn, request: Request, db: Session = Depends(get_db),
                      ctx: BusinessCtx = Depends(supplier_ctx("supplier.pricing.manage"))):
    pl = db.get(PriceList, pl_id)
    if pl is None or pl.supplier_id != ctx.business_id:
        raise NotFound()
    _save_price_list(db, ctx, pl, data)
    audit(db, "price_list.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="price_list",
          entity_id=pl.id, changes=data.model_dump(), request=request)
    db.commit()
    return price_list_out(pl)


@router.delete("/supplier/price-lists/{pl_id}")
def delete_price_list(pl_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      ctx: BusinessCtx = Depends(supplier_ctx("supplier.pricing.manage"))):
    pl = db.get(PriceList, pl_id)
    if pl is None or pl.supplier_id != ctx.business_id:
        raise NotFound()
    db.delete(pl)
    audit(db, "price_list.delete", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="price_list",
          entity_id=pl_id, request=request)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ promotions
class PromotionIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    name_ar: str | None = Field(default=None, max_length=160)
    kind: PromotionKind
    value: Decimal = Field(gt=0, le=100000)
    min_qty: int = Field(default=1, ge=1)
    offer_id: uuid.UUID | None = None
    category_id: int | None = None
    customer_business_ids: list[uuid.UUID] = []
    city_ids: list[int] = []
    starts_at: datetime
    ends_at: datetime
    is_active: bool = True

    @model_validator(mode="after")
    def _check(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.kind in (PromotionKind.percent, PromotionKind.quantity_tier) and self.value > 100:
            raise ValueError("percent cannot exceed 100")
        if self.kind == PromotionKind.quantity_tier and self.min_qty < 2:
            raise ValueError("quantity tier requires min_qty >= 2")
        return self


def promo_out(p: PriceRule) -> dict:
    return {"id": str(p.id), "name": p.name, "name_i18n": p.name_i18n, "kind": p.kind.value, "value": p.value,
            "min_qty": p.min_qty, "offer_id": str(p.supplier_product_id) if p.supplier_product_id else None,
            "category_id": p.category_id, "customer_business_ids": p.customer_business_ids, "city_ids": p.city_ids,
            "starts_at": p.starts_at, "ends_at": p.ends_at, "is_active": p.is_active}


def _apply_promo(db: Session, ctx: BusinessCtx, p: PriceRule, data: PromotionIn) -> None:
    if data.offer_id:
        sp = db.get(SupplierProduct, data.offer_id)
        if sp is None or sp.supplier_id != ctx.business_id:
            raise ValidationFailed("invalid_offer")
    if data.category_id:
        _check_category(db, data.category_id)
    p.name, p.kind, p.value, p.min_qty = data.name, data.kind, data.value, data.min_qty
    p.name_i18n = {"ar": data.name_ar or data.name, "en": data.name}
    p.supplier_product_id, p.category_id = data.offer_id, data.category_id
    p.customer_business_ids = [str(x) for x in data.customer_business_ids]
    p.city_ids = data.city_ids
    p.starts_at, p.ends_at, p.is_active = data.starts_at, data.ends_at, data.is_active


@router.get("/supplier/promotions")
def list_promotions(db: Session = Depends(get_db), ctx: BusinessCtx = Depends(supplier_ctx())):
    rows = db.scalars(select(PriceRule).where(PriceRule.supplier_id == ctx.business_id).order_by(PriceRule.starts_at.desc())).all()
    return [promo_out(p) for p in rows]


@router.post("/supplier/promotions", status_code=201)
def create_promotion(data: PromotionIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(supplier_ctx("supplier.pricing.manage"))):
    p = PriceRule(supplier_id=ctx.business_id, name=data.name, kind=data.kind, value=data.value,
                  starts_at=data.starts_at, ends_at=data.ends_at)
    _apply_promo(db, ctx, p, data)
    db.add(p)
    audit(db, "promotion.create", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="price_rule",
          entity_id=p.id, changes=data.model_dump(), request=request)
    db.commit()
    return promo_out(p)


@router.put("/supplier/promotions/{promo_id}")
def update_promotion(promo_id: uuid.UUID, data: PromotionIn, request: Request, db: Session = Depends(get_db),
                     ctx: BusinessCtx = Depends(supplier_ctx("supplier.pricing.manage"))):
    p = db.get(PriceRule, promo_id)
    if p is None or p.supplier_id != ctx.business_id:
        raise NotFound()
    _apply_promo(db, ctx, p, data)
    audit(db, "promotion.update", actor_user_id=ctx.user.id, actor_business_id=ctx.business_id, entity_type="price_rule",
          entity_id=p.id, changes=data.model_dump(), request=request)
    db.commit()
    return promo_out(p)


# ------------------------------------------------------------------ marketplace (any signed-in user)
def visible_suppliers_stmt():
    return select(Business).where(Business.type == BusinessType.supplier, Business.status == BusinessStatus.active,
                                  Business.verification_status == VerificationStatus.verified)


def buyer_context(db: Session, principal: Principal, request: Request) -> tuple[uuid.UUID | None, int | None]:
    """Retailer id & city for personalized prices (only if the caller is a member of that retailer)."""
    selector = request.headers.get("x-business-id")
    for m in principal.memberships:
        if m.business.type == BusinessType.retailer and (selector is None or str(m.business_id) == selector):
            city = m.business.city_id
            if m.branch_id:
                br = db.get(Branch, m.branch_id)
                city = br.city_id if br and br.city_id else city
            return m.business_id, city
    return None, None


@router.get("/market/suppliers")
def market_suppliers(request: Request, q: str | None = None, city_id: int | None = None, category_id: int | None = None,
                     params: PageParams = Depends(), db: Session = Depends(get_db),
                     principal: Principal = Depends(current_principal)):
    stmt = visible_suppliers_stmt().order_by(Business.rating_avg.desc(), Business.trade_name_ar)
    if q:
        stmt = stmt.where(or_(Business.trade_name_ar.ilike(f"%{q}%"), Business.trade_name_en.ilike(f"%{q}%")))
    if city_id:
        stmt = stmt.where(Business.id.in_(select(CoverageArea.supplier_id).where(CoverageArea.city_id == city_id,
                                                                                 CoverageArea.is_active.is_(True))))
    if category_id:
        stmt = stmt.where(Business.id.in_(select(SupplierProduct.supplier_id).join(Product).where(
            Product.category_id == category_id, SupplierProduct.is_active.is_(True))))
    loc = principal.locale
    page = paginate(db, stmt, params)
    ids = [b.id for b in page["items"]]
    counts = dict(db.execute(select(SupplierProduct.supplier_id, func.count()).where(
        SupplierProduct.supplier_id.in_(ids), SupplierProduct.is_active.is_(True)).group_by(SupplierProduct.supplier_id)).all()) if ids else {}
    page["items"] = [{**business_brief(b, loc), "min_order_value": b.min_order_value, "products_count": counts.get(b.id, 0),
                      "description": b.description} for b in page["items"]]
    return page


@router.get("/market/suppliers/{supplier_id}")
def market_supplier(supplier_id: uuid.UUID, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    b = db.scalar(visible_suppliers_stmt().where(Business.id == supplier_id))
    if b is None:
        raise NotFound()
    loc = principal.locale
    coverage = db.scalars(select(CoverageArea).where(CoverageArea.supplier_id == b.id, CoverageArea.is_active.is_(True))).all()
    cats = db.execute(select(Category, func.count()).join(Product, Product.category_id == Category.id).join(
        SupplierProduct, SupplierProduct.product_id == Product.id).where(SupplierProduct.supplier_id == b.id,
                                                                          SupplierProduct.is_active.is_(True)).group_by(Category.id)).all()
    return {**business_brief(b, loc), "description": b.description, "min_order_value": b.min_order_value,
            "supply_terms": b.supply_terms, "payment_terms": b.payment_terms, "phone": b.phone, "email": b.email,
            "website": b.website, "default_lead_time_days": b.default_lead_time_days,
            "coverage": [{"city": city_out(c.city, loc), "delivery_fee": c.delivery_fee, "min_order_value": c.min_order_value,
                          "lead_time_days": c.lead_time_days, "district": c.district} for c in coverage],
            "categories": [{"id": c.id, "name": localized(c.name, loc), "count": n} for c, n in cats]}


def _market_offers_stmt():
    return (select(SupplierProduct).join(Product, Product.id == SupplierProduct.product_id)
            .join(Business, Business.id == SupplierProduct.supplier_id)
            .where(SupplierProduct.is_active.is_(True), Product.status == ProductStatus.active,
                   Business.status == BusinessStatus.active, Business.verification_status == VerificationStatus.verified))


@router.get("/market/offers")
def market_offers(request: Request, supplier_id: uuid.UUID | None = None, q: str | None = None,
                  category_id: int | None = None, brand_id: uuid.UUID | None = None,
                  in_stock: bool = False, sort: Literal["name", "price_asc", "price_desc", "newest"] = "name",
                  params: PageParams = Depends(), db: Session = Depends(get_db),
                  principal: Principal = Depends(current_principal)):
    stmt = apply_search(_market_offers_stmt(), q)
    if supplier_id:
        stmt = stmt.where(SupplierProduct.supplier_id == supplier_id)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    if in_stock:
        stmt = stmt.where(SupplierProduct.availability.in_([Availability.in_stock, Availability.low_stock]))
    order = {"name": Product.name_ar if principal.locale == "ar" else Product.name_en,
             "price_asc": SupplierProduct.unit_price, "price_desc": SupplierProduct.unit_price.desc(),
             "newest": SupplierProduct.created_at.desc()}[sort]
    stmt = stmt.order_by(order, SupplierProduct.id)
    retailer_id, city_id = buyer_context(db, principal, request)
    page = paginate(db, stmt, params)
    ctxs: dict[uuid.UUID, PricingContext] = {}
    suppliers = {b.id: b for b in db.scalars(select(Business).where(Business.id.in_({sp.supplier_id for sp in page["items"]})))}
    items = []
    for sp in page["items"]:
        pc = ctxs.get(sp.supplier_id) or ctxs.setdefault(sp.supplier_id, PricingContext(db, sp.supplier_id, retailer_id, city_id))
        items.append(offer_out(sp, principal.locale, pc, suppliers.get(sp.supplier_id)))
    page["items"] = items
    return page


@router.get("/market/products")
def market_products(q: str | None = None, category_id: int | None = None, brand_id: uuid.UUID | None = None,
                    params: PageParams = Depends(), db: Session = Depends(get_db),
                    principal: Principal = Depends(current_principal)):
    """Product-level search with offer summary (count, best price) for comparison."""
    offers = _market_offers_stmt().subquery()
    stmt = select(Product).where(Product.id.in_(select(offers.c.product_id)), Product.status == ProductStatus.active)
    stmt = apply_search(stmt, q)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand_id:
        stmt = stmt.where(Product.brand_id == brand_id)
    stmt = stmt.order_by(Product.name_ar if principal.locale == "ar" else Product.name_en)
    page = paginate(db, stmt, params)
    ids = [p.id for p in page["items"]]
    summary = {}
    if ids:
        rows = db.execute(select(offers.c.product_id, func.count(), func.min(offers.c.unit_price)).where(
            offers.c.product_id.in_(ids)).group_by(offers.c.product_id)).all()
        summary = {pid: (n, mn) for pid, n, mn in rows}
    page["items"] = [{**product_out(p, principal.locale), "offers_count": summary.get(p.id, (0, None))[0],
                      "min_unit_price": summary.get(p.id, (0, None))[1]} for p in page["items"]]
    return page


@router.get("/market/products/{product_id}")
def market_product(product_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)):
    p = db.get(Product, product_id)
    if p is None or p.status != ProductStatus.active:
        raise NotFound()
    retailer_id, city_id = buyer_context(db, principal, request)
    offers = db.scalars(_market_offers_stmt().where(SupplierProduct.product_id == p.id)).all()
    out = []
    for sp in offers:
        sup = db.get(Business, sp.supplier_id)
        pc = PricingContext(db, sp.supplier_id, retailer_id, city_id)
        o = offer_out(sp, principal.locale, pc, sup)
        if city_id:
            cov = db.scalar(select(CoverageArea).where(CoverageArea.supplier_id == sp.supplier_id, CoverageArea.city_id == city_id,
                                                       CoverageArea.is_active.is_(True)))
            o["delivers_to_you"] = cov is not None
            o["delivery_fee"] = cov.delivery_fee if cov else None
        out.append(o)
    out.sort(key=lambda o: (o["availability"] in ("out_of_stock", "discontinued"), o["price"]["piece"]["net"]))
    return {"product": product_out(p, principal.locale), "offers": out}


# ------------------------------------------------------------------ representative: authorized catalog
@router.get("/rep/catalog")
def rep_catalog(request: Request, supplier_id: uuid.UUID | None = None, q: str | None = None, category_id: int | None = None,
                retailer_id: uuid.UUID | None = None, params: PageParams = Depends(), db: Session = Depends(get_db),
                principal: Principal = Depends(current_principal)):
    """Offers the representative is currently authorized to sell (effective authorizations only)."""
    from app.core.db import set_rls_context
    from app.models.reps import Authorization
    from app.models.enums import AuthorizationStatus
    from app.modules.authorizations.service import authorized_scope_filter, is_effective

    if principal.rep is None:
        raise Forbidden("not_a_representative")
    set_rls_context(db, user_id=principal.id, rep_id=principal.rep.id)
    auths = [a for a in db.scalars(select(Authorization).where(Authorization.representative_id == principal.rep.id,
                                                               Authorization.status == AuthorizationStatus.active))
             if is_effective(a) and a.type.value != "promotion_only" and (supplier_id is None or a.supplier_id == supplier_id)]
    if not auths:
        return {"items": [], "total": 0, "page": params.page, "page_size": params.page_size, "authorizations": []}
    conds = []
    for a in auths:
        f = authorized_scope_filter(a)
        conds.append(and_(SupplierProduct.supplier_id == a.supplier_id, *( [f] if f is not None else [])))
    stmt = apply_search(_market_offers_stmt().where(or_(*conds)), q)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    stmt = stmt.order_by(Product.name_ar if principal.locale == "ar" else Product.name_en, SupplierProduct.id)
    city_id = None
    if retailer_id:
        with system_context(db):
            r = db.get(Business, retailer_id)
            if r is not None and r.type == BusinessType.retailer:
                city_id = r.city_id
            else:
                retailer_id = None
    page = paginate(db, stmt, params)
    suppliers = {b.id: b for b in db.scalars(select(Business).where(Business.id.in_({a.supplier_id for a in auths})))}
    ctxs: dict = {}
    items = []
    for sp in page["items"]:
        pc = ctxs.get(sp.supplier_id) or ctxs.setdefault(sp.supplier_id, PricingContext(db, sp.supplier_id, retailer_id, city_id))
        items.append(offer_out(sp, principal.locale, pc, suppliers.get(sp.supplier_id)))
    page["items"] = items
    page["authorizations"] = [{"id": str(a.id), "number": a.number, "supplier_id": str(a.supplier_id),
                               "supplier": business_brief(suppliers.get(a.supplier_id), principal.locale),
                               "end_date": a.end_date} for a in auths]
    return page
