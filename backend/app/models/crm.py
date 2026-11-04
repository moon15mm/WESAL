"""CRM: customers are per-owner records (supplier or representative) about a store.
A store may be a registered retailer business or an unregistered lead."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import (
    AcquisitionSource,
    CustomerStatus,
    OpportunityStage,
    VisitOutcome,
    VisitPurpose,
    VisitStatus,
    db_enum,
)


class Customer(UUIDPk, Timestamps, Base):
    __tablename__ = "customers"

    owner_supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    owner_representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_branches.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), index=True)
    district: Mapped[str | None] = mapped_column(String(120))
    address_line: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    status: Mapped[CustomerStatus] = mapped_column(db_enum(CustomerStatus, "customer_status"), default=CustomerStatus.lead, index=True)
    source: Mapped[AcquisitionSource] = mapped_column(db_enum(AcquisitionSource, "customer_source"))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    assigned_representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id", ondelete="SET NULL"), index=True)
    favorite_product_ids: Mapped[list] = mapped_column(JSONB, default=list)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    total_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    city: Mapped["City | None"] = relationship(lazy="joined")  # noqa: F821

    __table_args__ = (
        CheckConstraint("(owner_supplier_id IS NULL) <> (owner_representative_id IS NULL)", name="one_owner"),
        Index("uq_customer_supplier_retailer", "owner_supplier_id", "retailer_id", unique=True,
              postgresql_where="owner_supplier_id IS NOT NULL AND retailer_id IS NOT NULL"),
        Index("uq_customer_rep_retailer", "owner_representative_id", "retailer_id", unique=True,
              postgresql_where="owner_representative_id IS NOT NULL AND retailer_id IS NOT NULL"),
    )


class CustomerContact(UUIDPk, Base):
    __tablename__ = "customer_contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))


class CustomerNote(UUIDPk, Base):
    __tablename__ = "customer_notes"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerAcquisition(UUIDPk, Base):
    """customer_acquisition_records: immutable record of how a supplier acquired a retailer.
    Changes go through customer_source_changes (permission + reason)."""

    __tablename__ = "customer_acquisition_records"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id", ondelete="SET NULL"), index=True)
    source: Mapped[AcquisitionSource] = mapped_column(db_enum(AcquisitionSource, "acquisition_source"))
    first_order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (Index("uq_acq_supplier_retailer", "supplier_id", "retailer_id", unique=True),)


class CustomerSourceChange(UUIDPk, Base):
    __tablename__ = "customer_source_changes"

    acquisition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customer_acquisition_records.id", ondelete="CASCADE"), index=True)
    old_source: Mapped[str | None] = mapped_column(String(40))
    new_source: Mapped[str | None] = mapped_column(String(40))
    old_representative_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    new_representative_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomerAssignment(UUIDPk, Base):
    __tablename__ = "customer_assignments"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Opportunity(UUIDPk, Timestamps, Base):
    __tablename__ = "opportunities"

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    owner_supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    owner_representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    stage: Mapped[OpportunityStage] = mapped_column(db_enum(OpportunityStage, "opportunity_stage"), default=OpportunityStage.open)
    expected_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class Visit(UUIDPk, Timestamps, Base):
    __tablename__ = "visits"

    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    retailer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_branches.id", ondelete="SET NULL"))
    purpose: Mapped[VisitPurpose] = mapped_column(db_enum(VisitPurpose, "visit_purpose"))
    status: Mapped[VisitStatus] = mapped_column(db_enum(VisitStatus, "visit_status"), default=VisitStatus.scheduled, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # location captured only with explicit consent at start/end of a visit
    start_lat: Mapped[float | None] = mapped_column(Float)
    start_lng: Mapped[float | None] = mapped_column(Float)
    end_lat: Mapped[float | None] = mapped_column(Float)
    end_lng: Mapped[float | None] = mapped_column(Float)
    location_consent: Mapped[bool] = mapped_column(default=False)
    outcome: Mapped[VisitOutcome | None] = mapped_column(db_enum(VisitOutcome, "visit_outcome"))
    notes: Mapped[str | None] = mapped_column(Text)
    discussed_products: Mapped[list] = mapped_column(JSONB, default=list)  # [{product_id, feedback}]
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    next_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer | None"] = relationship(lazy="joined")
