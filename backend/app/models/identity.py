from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import Channel, RoleScope, UserStatus, VerificationPurpose, db_enum


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[UserStatus] = mapped_column(db_enum(UserStatus, "user_status"), default=UserStatus.active)
    locale: Mapped[str] = mapped_column(String(8), default="ar")
    document_locale: Mapped[str | None] = mapped_column(String(8))
    number_system: Mapped[str] = mapped_column(String(8), default="latn")  # latn | arab
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Riyadh")
    currency: Mapped[str] = mapped_column(String(3), default="SAR")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text)
    mfa_recovery_hashes: Mapped[list | None] = mapped_column(JSONB)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_version: Mapped[str | None] = mapped_column(String(20))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_reason: Mapped[str | None] = mapped_column(Text)
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", use_alter=True))

    roles: Mapped[list["UserRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index("uq_users_email_lower", func.lower(email), unique=True, postgresql_where=email.isnot(None)),
        Index("uq_users_phone", phone, unique=True, postgresql_where=phone.isnot(None)),
    )


class UserSession(UUIDPk, Base):
    __tablename__ = "sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    device_label: Mapped[str | None] = mapped_column(String(120))

    user: Mapped[User] = relationship()


class VerificationCode(UUIDPk, Base):
    """verification_records: OTPs / email tokens (hashed)."""

    __tablename__ = "verification_records"

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[VerificationPurpose] = mapped_column(db_enum(VerificationPurpose, "verification_purpose"))
    channel: Mapped[Channel] = mapped_column(db_enum(Channel, "verification_channel"))
    target: Mapped[str] = mapped_column(String(254))
    code_hash: Mapped[str] = mapped_column(String(128))
    reference_id: Mapped[str | None] = mapped_column(String(64))  # e.g. order id for approval OTP
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Permission(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    module: Mapped[str] = mapped_column(String(40))
    scope: Mapped[RoleScope] = mapped_column(db_enum(RoleScope, "permission_scope"))


class Role(UUIDPk, Timestamps, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(60))
    scope: Mapped[RoleScope] = mapped_column(db_enum(RoleScope, "role_scope"))
    name: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"ar": "...", "en": "..."}
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)
    # custom roles belong to a business; system roles have NULL
    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))

    permissions: Mapped[list["RolePermission"]] = relationship(cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (UniqueConstraint("code", "business_id", name="uq_roles_code_business"),)

    @property
    def permission_codes(self) -> set[str]:
        return {p.permission_code for p in self.permissions}


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_code: Mapped[str] = mapped_column(ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True)


class UserRole(Base):
    """Platform-level roles (platform admin, support, ...)."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship(lazy="joined")
