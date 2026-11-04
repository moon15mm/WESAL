from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import CommissionStatus, DisputeStatus, db_enum


class Commission(UUIDPk, Timestamps, Base):
    __tablename__ = "commissions"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id"), index=True)
    authorization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authorizations.id"))
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commission_agreements.id"))
    status: Mapped[CommissionStatus] = mapped_column(db_enum(CommissionStatus, "commission_status"), index=True)
    eligible_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # qualifying sales value
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # current amount (after adjustments)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    breakdown: Mapped[list] = mapped_column(JSONB, default=list)  # per-line: rule_id, basis, rate, base, amount
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status_reason: Mapped[str | None] = mapped_column(Text)

    adjustments: Mapped[list["CommissionAdjustment"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        # prevents double calculation for the same order/representative/agreement
        Index("uq_commission_order_rep", "order_id", "representative_id", unique=True),
        CheckConstraint("amount >= 0", name="commission_nonneg"),
    )


class CommissionAdjustment(UUIDPk, Base):
    __tablename__ = "commission_adjustments"

    commission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commissions.id", ondelete="CASCADE"), index=True)
    amount_delta: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(String(40))  # return | cancellation | dispute_resolution | manual
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # return id / dispute id
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # an event (e.g. a return) can adjust a commission only once
        Index("uq_commission_adjustment_ref", "commission_id", "reason", "reference_id", unique=True,
              postgresql_where="reference_id IS NOT NULL"),
    )


class CommissionPayment(UUIDPk, Base):
    """Off-platform payout evidence recorded by the supplier."""

    __tablename__ = "commission_payments"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    commission_ids: Mapped[list] = mapped_column(JSONB)
    method: Mapped[str] = mapped_column(String(30))
    reference: Mapped[str | None] = mapped_column(String(120))
    proof_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("amount > 0", name="payout_pos"),)


class CommissionDispute(UUIDPk, Timestamps, Base):
    __tablename__ = "commission_disputes"

    commission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commissions.id", ondelete="CASCADE"), index=True)
    raised_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text)
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[DisputeStatus] = mapped_column(db_enum(DisputeStatus, "commission_dispute_status"), default=DisputeStatus.open)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
