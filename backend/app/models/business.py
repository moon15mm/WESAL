from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
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
    BusinessStatus,
    BusinessType,
    DocumentStatus,
    FilePurpose,
    MemberStatus,
    VerificationStatus,
    db_enum,
)


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[dict] = mapped_column(JSONB)


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[dict] = mapped_column(JSONB)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    region: Mapped[Region] = relationship(lazy="joined")


class StoredFile(UUIDPk, Base):
    __tablename__ = "files"

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="SET NULL"), index=True)
    purpose: Mapped[FilePurpose] = mapped_column(db_enum(FilePurpose, "file_purpose"))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Business(UUIDPk, Timestamps, Base):
    __tablename__ = "businesses"

    type: Mapped[BusinessType] = mapped_column(db_enum(BusinessType, "business_type"), index=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    trade_name_ar: Mapped[str] = mapped_column(String(200))
    trade_name_en: Mapped[str | None] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    cr_number: Mapped[str | None] = mapped_column(String(20))
    vat_number: Mapped[str | None] = mapped_column(String(20))
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    activity: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL", use_alter=True))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    website: Mapped[str | None] = mapped_column(String(200))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), index=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        db_enum(VerificationStatus, "business_verification"), default=VerificationStatus.unverified, index=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BusinessStatus] = mapped_column(db_enum(BusinessStatus, "business_status"), default=BusinessStatus.active)
    # supplier commerce settings
    min_order_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    supply_terms: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    default_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    # retailer settings
    discoverable: Mapped[bool] = mapped_column(Boolean, default=True)  # can reps discover this store
    store_type: Mapped[str | None] = mapped_column(String(40))  # grocery, minimarket, supermarket
    rating_avg: Mapped[float] = mapped_column(Float, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    branches: Mapped[list["Branch"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    city: Mapped["City | None"] = relationship(lazy="joined")

    __table_args__ = (
        Index("uq_businesses_cr_type", "cr_number", "type", unique=True, postgresql_where=cr_number.isnot(None)),
    )

    def display_name(self, locale: str = "ar") -> str:
        if locale != "ar" and self.trade_name_en:
            return self.trade_name_en
        return self.trade_name_ar


class Branch(UUIDPk, Timestamps, Base):
    __tablename__ = "business_branches"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str | None] = mapped_column(String(30))
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), index=True)
    district: Mapped[str | None] = mapped_column(String(120))
    address_line: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(20))
    working_hours: Mapped[dict | None] = mapped_column(JSONB)
    manager_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    business: Mapped[Business] = relationship(back_populates="branches")
    city: Mapped["City | None"] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("business_id", "code", name="uq_branch_code"),)


class BusinessAddress(UUIDPk, Timestamps, Base):
    __tablename__ = "business_addresses"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="headquarters")  # headquarters | warehouse | billing
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"))
    district: Mapped[str | None] = mapped_column(String(120))
    address_line: Mapped[str] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    building_number: Mapped[str | None] = mapped_column(String(10))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)


class BusinessMember(UUIDPk, Timestamps, Base):
    """business_users: a user's membership in a business with a business-scoped role."""

    __tablename__ = "business_users"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_branches.id", ondelete="SET NULL"))
    status: Mapped[MemberStatus] = mapped_column(db_enum(MemberStatus, "member_status"), default=MemberStatus.active)
    title: Mapped[str | None] = mapped_column(String(120))
    invited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    business: Mapped[Business] = relationship(lazy="joined")
    role: Mapped["Role"] = relationship(lazy="joined")  # noqa: F821
    user: Mapped["User"] = relationship(lazy="joined")  # noqa: F821

    __table_args__ = (UniqueConstraint("business_id", "user_id", name="uq_business_member"),)


class BusinessDocument(UUIDPk, Timestamps, Base):
    __tablename__ = "business_documents"

    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))  # commercial_registration | vat_certificate | municipal_license | other
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    number: Mapped[str | None] = mapped_column(String(40))
    expires_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[DocumentStatus] = mapped_column(db_enum(DocumentStatus, "business_doc_status"), default=DocumentStatus.pending)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)


class CoverageArea(UUIDPk, Base):
    """Supplier delivery coverage per city (optionally per district)."""

    __tablename__ = "supplier_coverage_areas"

    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), index=True)
    district: Mapped[str | None] = mapped_column(String(120))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    min_order_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    lead_time_days: Mapped[int] = mapped_column(Integer, default=1)
    delivery_days: Mapped[list | None] = mapped_column(JSONB)  # [0..6]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    city: Mapped[City] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("supplier_id", "city_id", "district", name="uq_coverage"),)
