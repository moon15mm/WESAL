from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
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
    AuthorizationStatus,
    AuthorizationType,
    CommissionBasis,
    CommissionScope,
    DocumentStatus,
    Priority,
    RepAvailability,
    RepCompanyRelation,
    RepCompanyStatus,
    RepKind,
    TaskStatus,
    VerificationStatus,
    db_enum,
)


class Representative(UUIDPk, Timestamps, Base):
    __tablename__ = "representatives"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    kind: Mapped[RepKind] = mapped_column(db_enum(RepKind, "rep_kind"), default=RepKind.independent)
    display_name: Mapped[str] = mapped_column(String(160))
    headline: Mapped[str | None] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text)
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    skills: Mapped[list] = mapped_column(JSONB, default=list)
    languages: Mapped[list] = mapped_column(JSONB, default=list)
    availability: Mapped[RepAvailability] = mapped_column(db_enum(RepAvailability, "rep_availability"), default=RepAvailability.available)
    public_profile: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        db_enum(VerificationStatus, "rep_verification"), default=VerificationStatus.unverified, index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    freelance_doc_number: Mapped[str | None] = mapped_column(String(40))  # e.g. Saudi freelance certificate
    home_city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821
    areas: Mapped[list["RepresentativeArea"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    categories: Mapped[list["RepresentativeCategory"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class RepresentativeArea(UUIDPk, Base):
    __tablename__ = "representative_areas"

    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), index=True)
    district: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (UniqueConstraint("representative_id", "city_id", "district", name="uq_rep_area"),)


class RepresentativeCategory(Base):
    __tablename__ = "representative_categories"

    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True)


class RepresentativeDocument(UUIDPk, Timestamps, Base):
    __tablename__ = "representative_documents"

    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))  # national_id | freelance_certificate | other
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    status: Mapped[DocumentStatus] = mapped_column(db_enum(DocumentStatus, "rep_doc_status"), default=DocumentStatus.pending)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)


class RepresentativeCompany(UUIDPk, Timestamps, Base):
    """Relationship between a representative and a supplier company."""

    __tablename__ = "representative_companies"

    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    relation: Mapped[RepCompanyRelation] = mapped_column(db_enum(RepCompanyRelation, "rep_company_relation"))
    status: Mapped[RepCompanyStatus] = mapped_column(db_enum(RepCompanyStatus, "rep_company_status"), default=RepCompanyStatus.active)
    employee_code: Mapped[str | None] = mapped_column(String(40))
    supervisor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    representative: Mapped[Representative] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("representative_id", "supplier_id", name="uq_rep_company"),)


class CommissionAgreement(UUIDPk, Timestamps, Base):
    __tablename__ = "commission_agreements"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    eligible_after: Mapped[str] = mapped_column(String(20), default="completed")  # delivered | completed
    hold_days: Mapped[int] = mapped_column(Integer, default=7)  # return window before commission becomes due
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    rules: Mapped[list["CommissionRule"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="CommissionRule.priority")


class CommissionRule(UUIDPk, Base):
    __tablename__ = "commission_rules"

    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commission_agreements.id", ondelete="CASCADE"), index=True)
    basis: Mapped[CommissionBasis] = mapped_column(db_enum(CommissionBasis, "commission_basis"))
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))  # percent (e.g. 3.5) or SAR amount
    scope: Mapped[CommissionScope] = mapped_column(db_enum(CommissionScope, "commission_scope"), default=CommissionScope.all)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"))
    min_order_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    priority: Mapped[int] = mapped_column(Integer, default=100)

    __table_args__ = (
        CheckConstraint("rate >= 0", name="rate_nonneg"),
        CheckConstraint("basis <> 'percent' OR rate <= 100", name="pct_max"),
    )


class Authorization(UUIDPk, Timestamps, Base):
    __tablename__ = "authorizations"

    number: Mapped[str] = mapped_column(String(30), unique=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    type: Mapped[AuthorizationType] = mapped_column(db_enum(AuthorizationType, "authorization_type"), default=AuthorizationType.full_sales)
    status: Mapped[AuthorizationStatus] = mapped_column(db_enum(AuthorizationStatus, "authorization_status"), index=True)
    initiated_by: Mapped[str] = mapped_column(String(20))  # representative | supplier
    request_message: Mapped[str | None] = mapped_column(Text)
    agreement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("commission_agreements.id", ondelete="SET NULL"))
    all_products: Mapped[bool] = mapped_column(Boolean, default=False)
    all_areas: Mapped[bool] = mapped_column(Boolean, default=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    terms: Mapped[str | None] = mapped_column(Text)
    terms_hash: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status_reason: Mapped[str | None] = mapped_column(Text)
    expiry_warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewed_from_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("authorizations.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1)

    representative: Mapped[Representative] = relationship(lazy="joined")
    supplier: Mapped["Business"] = relationship(lazy="joined", foreign_keys=[supplier_id])  # noqa: F821
    agreement: Mapped["CommissionAgreement | None"] = relationship(lazy="joined")
    products: Mapped[list["AuthorizationProduct"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    areas: Mapped[list["AuthorizationArea"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="auth_dates"),)


class AuthorizationProduct(UUIDPk, Base):
    __tablename__ = "authorization_products"

    authorization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authorizations.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    brand_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"))

    __table_args__ = (
        CheckConstraint(
            "(product_id IS NOT NULL)::int + (category_id IS NOT NULL)::int + (brand_id IS NOT NULL)::int = 1",
            name="one_scope",
        ),
    )


class AuthorizationArea(UUIDPk, Base):
    __tablename__ = "authorization_areas"

    authorization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authorizations.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    district: Mapped[str | None] = mapped_column(String(120))


class AuthorizationHistory(UUIDPk, Base):
    __tablename__ = "authorization_history"

    authorization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authorizations.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RepTask(UUIDPk, Timestamps, Base):
    """Tasks assigned by a supplier to its representatives."""

    __tablename__ = "rep_tasks"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[Priority] = mapped_column(db_enum(Priority, "task_priority"), default=Priority.normal)
    status: Mapped[TaskStatus] = mapped_column(db_enum(TaskStatus, "task_status"), default=TaskStatus.open)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepTarget(UUIDPk, Timestamps, Base):
    __tablename__ = "rep_targets"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    sales_target: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    visits_target: Mapped[int] = mapped_column(Integer, default=0)
    new_customers_target: Mapped[int] = mapped_column(Integer, default=0)
