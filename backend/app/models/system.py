from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, Timestamps, UUIDPk
from app.models.enums import (
    AdStatus,
    Channel,
    ComplaintCategory,
    ComplaintKind,
    ComplaintStatus,
    DataRequestKind,
    DataRequestStatus,
    OutboxStatus,
    Priority,
    RatingStatus,
    RatingTarget,
    SubscriptionStatus,
    db_enum,
)


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(60))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    link: Mapped[str | None] = mapped_column(String(255))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("uq_notifications_dedupe", "user_id", "dedupe_key", unique=True, postgresql_where="dedupe_key IS NOT NULL"),
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    event: Mapped[str] = mapped_column(String(60), primary_key=True)
    channel: Mapped[Channel] = mapped_column(db_enum(Channel, "pref_channel"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationDelivery(UUIDPk, Base):
    """Transactional outbox for external channels; processed by the worker."""

    __tablename__ = "notification_deliveries"

    notification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[Channel] = mapped_column(db_enum(Channel, "delivery_channel"))
    target: Mapped[str | None] = mapped_column(String(254))
    template: Mapped[str] = mapped_column(String(60))
    locale: Mapped[str] = mapped_column(String(8), default="ar")
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[OutboxStatus] = mapped_column(db_enum(OutboxStatus, "outbox_status"), default=OutboxStatus.pending)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    provider_ref: Mapped[str | None] = mapped_column(String(120))
    dedupe_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_outbox_pending", "status", "next_attempt_at"),)


class PushSubscription(UUIDPk, Base):
    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Rating(UUIDPk, Timestamps, Base):
    __tablename__ = "ratings"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    rater_business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"))
    rater_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[RatingTarget] = mapped_column(db_enum(RatingTarget, "rating_target"))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    overall: Mapped[int] = mapped_column(SmallInteger)
    product_quality: Mapped[int | None] = mapped_column(SmallInteger)
    delivery_commitment: Mapped[int | None] = mapped_column(SmallInteger)
    communication: Mapped[int | None] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RatingStatus] = mapped_column(db_enum(RatingStatus, "rating_status"), default=RatingStatus.published)
    moderation_note: Mapped[str | None] = mapped_column(Text)
    reply: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("order_id", "rater_business_id", "target_type", name="uq_rating_per_order"),
        CheckConstraint("overall BETWEEN 1 AND 5", name="overall_range"),
        CheckConstraint("product_quality IS NULL OR product_quality BETWEEN 1 AND 5", name="pq_range"),
        CheckConstraint("delivery_commitment IS NULL OR delivery_commitment BETWEEN 1 AND 5", name="dc_range"),
        CheckConstraint("communication IS NULL OR communication BETWEEN 1 AND 5", name="comm_range"),
    )


class RatingReport(UUIDPk, Base):
    __tablename__ = "rating_reports"

    rating_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ratings.id", ondelete="CASCADE"), index=True)
    reported_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Complaint(UUIDPk, Timestamps, Base):
    __tablename__ = "complaints"

    number: Mapped[str] = mapped_column(String(30), unique=True)
    kind: Mapped[ComplaintKind] = mapped_column(db_enum(ComplaintKind, "complaint_kind"))
    category: Mapped[ComplaintCategory] = mapped_column(db_enum(ComplaintCategory, "complaint_category"))
    status: Mapped[ComplaintStatus] = mapped_column(db_enum(ComplaintStatus, "complaint_status"), default=ComplaintStatus.open, index=True)
    priority: Mapped[Priority] = mapped_column(db_enum(Priority, "complaint_priority"), default=Priority.normal)
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"), index=True)
    raised_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    raised_by_business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"), index=True)
    against_business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id"), index=True)
    against_representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id"), index=True)
    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    attachment_file_ids: Mapped[list] = mapped_column(JSONB, default=list)
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    order_status_before: Mapped[str | None] = mapped_column(String(40))

    messages: Mapped[list["ComplaintMessage"]] = relationship(cascade="all, delete-orphan", lazy="selectin", order_by="ComplaintMessage.created_at")


class ComplaintMessage(UUIDPk, Base):
    __tablename__ = "complaint_messages"

    complaint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_side: Mapped[str] = mapped_column(String(20))  # complainant | respondent | admin
    body: Mapped[str] = mapped_column(Text)
    internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Append-only audit log (UPDATE/DELETE blocked by a trigger)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    actor_business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20), default="success")  # success | denied | failed
    changes: Mapped[dict | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    request_id: Mapped[str | None] = mapped_column(String(64))

    # the runtime role can append but cannot read audit rows (RLS), so never use RETURNING
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"), {"implicit_returning": False})


class SubscriptionPlan(UUIDPk, Timestamps, Base):
    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    audience: Mapped[str] = mapped_column(String(20))  # supplier | retailer | representative
    name: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[dict] = mapped_column(JSONB, default=dict)
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    price_yearly: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    features: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Subscription(UUIDPk, Timestamps, Base):
    __tablename__ = "subscriptions"

    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    representative_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("representatives.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id"))
    status: Mapped[SubscriptionStatus] = mapped_column(db_enum(SubscriptionStatus, "subscription_status"))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    plan: Mapped[SubscriptionPlan] = relationship(lazy="joined")


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Advertisement(UUIDPk, Timestamps, Base):
    __tablename__ = "advertisements"

    business_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    placement: Mapped[str] = mapped_column(String(40))  # retailer_dashboard | marketplace_top | rep_dashboard
    title: Mapped[dict] = mapped_column(JSONB)
    body: Mapped[dict] = mapped_column(JSONB, default=dict)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    link_url: Mapped[str | None] = mapped_column(String(255))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[AdStatus] = mapped_column(db_enum(AdStatus, "ad_status"), default=AdStatus.draft)
    city_ids: Mapped[list] = mapped_column(JSONB, default=list)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)


class ContentPage(UUIDPk, Timestamps, Base):
    __tablename__ = "content_pages"

    slug: Mapped[str] = mapped_column(String(80))
    locale: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)  # markdown
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (UniqueConstraint("slug", "locale", name="uq_content_slug_locale"),)


class Language(Base):
    __tablename__ = "languages"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    native_name: Mapped[str] = mapped_column(String(60))
    direction: Mapped[str] = mapped_column(String(3))  # rtl | ltr
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class TranslationOverride(UUIDPk, Base):
    __tablename__ = "translation_overrides"

    locale: Mapped[str] = mapped_column(ForeignKey("languages.code", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("locale", "key", name="uq_translation_override"),)


class AIInteraction(UUIDPk, Base):
    __tablename__ = "ai_interactions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    feature: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(20))
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataRequest(UUIDPk, Timestamps, Base):
    """PDPL data subject requests (export / deletion)."""

    __tablename__ = "data_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[DataRequestKind] = mapped_column(db_enum(DataRequestKind, "data_request_kind"))
    status: Mapped[DataRequestStatus] = mapped_column(db_enum(DataRequestStatus, "data_request_status"), default=DataRequestStatus.pending)
    reason: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)


class ContactMessage(UUIDPk, Base):
    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    audience: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRun(UUIDPk, Base):
    """Scheduler heartbeat & run log (for monitoring)."""

    __tablename__ = "job_runs"

    job: Mapped[str] = mapped_column(String(60), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success: Mapped[bool | None] = mapped_column(Boolean)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
