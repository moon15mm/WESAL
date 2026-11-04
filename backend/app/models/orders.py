from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import (
    ApprovalDecision,
    ApprovalMethod,
    DeliveryStatus,
    OfferStatus,
    OrderChannel,
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    SaleUnit,
    db_enum,
)


class Cart(UUIDPk, Timestamps, Base):
    """One open cart per (user, retailer, branch, supplier)."""

    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_branches.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["CartItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (UniqueConstraint("user_id", "retailer_id", "supplier_id", name="uq_cart"),)


class CartItem(UUIDPk, Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_products.id", ondelete="CASCADE"))
    unit: Mapped[SaleUnit] = mapped_column(db_enum(SaleUnit, "cart_unit"))
    quantity: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("cart_id", "supplier_product_id", "unit", name="uq_cart_item"),
        CheckConstraint("quantity > 0", name="cart_qty_pos"),
    )


class Order(UUIDPk, Timestamps, Base):
    __tablename__ = "orders"

    number: Mapped[str] = mapped_column(String(30), unique=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_branches.id", ondelete="SET NULL"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    channel: Mapped[OrderChannel] = mapped_column(db_enum(OrderChannel, "order_channel"))
    status: Mapped[OrderStatus] = mapped_column(db_enum(OrderStatus, "order_status"), index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id"), index=True)
    authorization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("authorizations.id"))
    visit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    supplier_notes: Mapped[str | None] = mapped_column(Text)
    # versioning for approvals: any change to items/prices increments version
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_version: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_reason: Mapped[str | None] = mapped_column(Text)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    payment_status: Mapped[PaymentStatus] = mapped_column(db_enum(PaymentStatus, "payment_status"), default=PaymentStatus.unpaid)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    invoice_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    invoice_number: Mapped[str | None] = mapped_column(String(60))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))

    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="OrderItem.position")
    retailer: Mapped["Business"] = relationship(foreign_keys=[retailer_id], lazy="joined")  # noqa: F821
    supplier: Mapped["Business"] = relationship(foreign_keys=[supplier_id], lazy="joined")  # noqa: F821
    branch: Mapped["Branch | None"] = relationship(lazy="joined")  # noqa: F821
    representative: Mapped["Representative | None"] = relationship(lazy="joined")  # noqa: F821

    __table_args__ = (
        Index("uq_orders_idempotency", "created_by_user_id", "idempotency_key", unique=True,
              postgresql_where="idempotency_key IS NOT NULL"),
        Index("ix_orders_supplier_status_created", "supplier_id", "status", "created_at"),
        Index("ix_orders_retailer_created", "retailer_id", "created_at"),
        CheckConstraint("total >= 0", name="total_nonneg"),
        CheckConstraint("channel <> 'representative' OR representative_id IS NOT NULL", name="rep_channel_has_rep"),
    )


class OrderItem(UUIDPk, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    supplier_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("supplier_products.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    name_ar: Mapped[str] = mapped_column(String(255))
    name_en: Mapped[str] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[SaleUnit] = mapped_column(db_enum(SaleUnit, "order_item_unit"))
    pieces_per_unit: Mapped[int] = mapped_column(Integer, default=1)
    quantity: Mapped[int] = mapped_column(Integer)
    list_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # catalog price at time of order
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # agreed price (after offer)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)  # per line
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    delivered_qty: Mapped[int | None] = mapped_column(Integer)
    returned_qty: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[int | None] = mapped_column(Integer)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        CheckConstraint("quantity > 0", name="qty_pos"),
        CheckConstraint("unit_price >= 0", name="price_nonneg"),
        CheckConstraint("returned_qty >= 0", name="returned_nonneg"),
    )


class OrderStatusHistory(UUIDPk, Base):
    """Append-only (protected by a DB trigger)."""

    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_role: Mapped[str | None] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderApproval(UUIDPk, Base):
    """Retailer approval record for a specific version of an order."""

    __tablename__ = "order_approvals"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))  # rep_order | offer | change
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decision: Mapped[ApprovalDecision] = mapped_column(db_enum(ApprovalDecision, "approval_decision"), default=ApprovalDecision.pending)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    method: Mapped[ApprovalMethod | None] = mapped_column(db_enum(ApprovalMethod, "approval_method"))
    comment: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (Index("ix_order_approvals_pending", "order_id", "decision"),)


class OrderOffer(UUIDPk, Base):
    """Supplier price offer (quotation) on an order."""

    __tablename__ = "order_offers"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[OfferStatus] = mapped_column(db_enum(OfferStatus, "offer_status"), default=OfferStatus.pending)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrderOfferItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class OrderOfferItem(UUIDPk, Base):
    __tablename__ = "order_offer_items"

    offer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_offers.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    __table_args__ = (CheckConstraint("quantity >= 0", name="offer_qty_nonneg"),)


class DeliveryRecord(UUIDPk, Timestamps, Base):
    __tablename__ = "delivery_records"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    status: Mapped[DeliveryStatus] = mapped_column(db_enum(DeliveryStatus, "delivery_status"), default=DeliveryStatus.pending)
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    driver_name: Mapped[str | None] = mapped_column(String(160))
    driver_phone: Mapped[str | None] = mapped_column(String(20))
    vehicle_plate: Mapped[str | None] = mapped_column(String(20))
    proof_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)


class DeliveryConfirmation(UUIDPk, Base):
    __tablename__ = "delivery_confirmations"

    delivery_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("delivery_records.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    receiver_name: Mapped[str | None] = mapped_column(String(160))
    items: Mapped[list] = mapped_column(JSONB)  # [{order_item_id, received_qty, damaged_qty}]
    has_shortage: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderCollection(UUIDPk, Base):
    """Off-platform payment collection evidence recorded by the supplier."""

    __tablename__ = "order_collections"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str] = mapped_column(String(30))  # cash | bank_transfer | cheque | pos | other
    reference: Mapped[str | None] = mapped_column(String(120))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    proof_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("amount > 0", name="collection_pos"),)


class ReturnRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "returns"

    number: Mapped[str] = mapped_column(String(30), unique=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(String(40))  # damaged | expired | wrong_item | quality | excess | other
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReturnStatus] = mapped_column(db_enum(ReturnStatus, "return_status"), default=ReturnStatus.requested, index=True)
    evidence_file_ids: Mapped[list] = mapped_column(JSONB, default=list)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)
    settlement_note: Mapped[str | None] = mapped_column(Text)  # settlement happens off-platform
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    items: Mapped[list["ReturnItem"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ReturnItem(UUIDPk, Base):
    __tablename__ = "return_items"

    return_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("returns.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    approved_quantity: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(40))

    __table_args__ = (CheckConstraint("quantity > 0", name="return_qty_pos"),)


class OrderSequence(Base):
    """Per-year counters for human-readable numbers (orders, returns, authorizations...)."""

    __tablename__ = "number_sequences"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
