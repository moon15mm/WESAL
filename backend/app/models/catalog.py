"""Catalog: product identity (products) is separated from commercial offers
(supplier_products). The same product can be offered by many suppliers at
different prices."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import Availability, PriceListType, ProductStatus, PromotionKind, SaleUnit, db_enum


class Category(Base, Timestamps):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[dict] = mapped_column(JSONB)  # {"ar","en","ur","hi"}
    icon: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Brand(UUIDPk, Timestamps, Base):
    __tablename__ = "brands"

    name_ar: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(2))
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    owner_business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Product(UUIDPk, Timestamps, Base):
    __tablename__ = "products"

    name_ar: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)  # optional ur / hi names
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    barcode: Mapped[str | None] = mapped_column(String(32))
    base_sku: Mapped[str | None] = mapped_column(String(64))
    package_size: Mapped[str | None] = mapped_column(String(40))  # e.g. "330 ml", "1 kg"
    pieces_per_carton: Mapped[int] = mapped_column(Integer, default=1)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    status: Mapped[ProductStatus] = mapped_column(db_enum(ProductStatus, "product_status"), default=ProductStatus.active, index=True)
    created_by_business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"))
    # normalized (Arabic-folded, lower-case) text for trigram search
    search_text: Mapped[str] = mapped_column(Text, default="")

    brand: Mapped["Brand | None"] = relationship(lazy="joined")
    category: Mapped[Category] = relationship(lazy="joined")
    units: Mapped[list["ProductUnit"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("uq_products_barcode", "barcode", unique=True, postgresql_where=barcode.isnot(None)),
        Index("ix_products_search_trgm", "search_text", postgresql_using="gin", postgresql_ops={"search_text": "gin_trgm_ops"}),
    )


class ProductUnit(UUIDPk, Base):
    """Packaging levels for a product (piece, carton, ...)."""

    __tablename__ = "product_units"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    unit: Mapped[SaleUnit] = mapped_column(db_enum(SaleUnit, "product_unit"))
    pieces: Mapped[int] = mapped_column(Integer, default=1)
    barcode: Mapped[str | None] = mapped_column(String(32))

    __table_args__ = (UniqueConstraint("product_id", "unit", name="uq_product_unit"),)


class SupplierProduct(UUIDPk, Timestamps, Base):
    """A supplier's commercial offer for a product."""

    __tablename__ = "supplier_products"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str | None] = mapped_column(String(64))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    carton_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    pieces_per_carton: Mapped[int] = mapped_column(Integer, default=1)
    sell_by_piece: Mapped[bool] = mapped_column(Boolean, default=True)
    sell_by_carton: Mapped[bool] = mapped_column(Boolean, default=True)
    min_order_qty: Mapped[int] = mapped_column(Integer, default=1)
    availability: Mapped[Availability] = mapped_column(db_enum(Availability, "availability"), default=Availability.in_stock)
    stock_qty: Mapped[int | None] = mapped_column(Integer)  # pieces; optional
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    price_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("supplier_id", "product_id", name="uq_supplier_product"),
        CheckConstraint("unit_price >= 0", name="unit_price_nonneg"),
        CheckConstraint("carton_price IS NULL OR carton_price >= 0", name="carton_price_nonneg"),
        CheckConstraint("pieces_per_carton >= 1", name="ppc_positive"),
        CheckConstraint("min_order_qty >= 1", name="moq_positive"),
    )


class PriceList(UUIDPk, Timestamps, Base):
    __tablename__ = "price_lists"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[PriceListType] = mapped_column(db_enum(PriceListType, "price_list_type"))
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    priority: Mapped[int] = mapped_column(Integer, default=100)  # lower wins
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # targets
    customer_business_ids: Mapped[list] = mapped_column(JSONB, default=list)
    city_ids: Mapped[list] = mapped_column(JSONB, default=list)

    items: Mapped[list["PriceListItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PriceListItem(UUIDPk, Base):
    __tablename__ = "price_list_items"

    price_list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("price_lists.id", ondelete="CASCADE"), index=True)
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_products.id", ondelete="CASCADE"), index=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    carton_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    __table_args__ = (
        UniqueConstraint("price_list_id", "supplier_product_id", name="uq_price_list_item"),
        CheckConstraint("unit_price >= 0", name="pli_price_nonneg"),
    )


class PriceRule(UUIDPk, Timestamps, Base):
    """Promotions: temporary discounts, quantity offers."""

    __tablename__ = "price_rules"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    kind: Mapped[PromotionKind] = mapped_column(db_enum(PromotionKind, "promotion_kind"))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    min_qty: Mapped[int] = mapped_column(Integer, default=1)  # in pieces
    supplier_product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supplier_products.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    customer_business_ids: Mapped[list] = mapped_column(JSONB, default=list)
    city_ids: Mapped[list] = mapped_column(JSONB, default=list)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("value >= 0", name="rule_value_nonneg"),
        CheckConstraint("ends_at > starts_at", name="rule_dates"),
        CheckConstraint("kind <> 'percent' OR value <= 100", name="rule_pct_max"),
    )
