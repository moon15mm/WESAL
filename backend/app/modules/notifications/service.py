"""Unified notification center.

`notify()` writes in-app notifications and enqueues external deliveries in the
same DB transaction as the business change (transactional outbox). The worker
(`app.workers.worker`) delivers the outbox with retries. Deduplication keys
prevent duplicate notifications for the same event."""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.db import system_context
from app.core.i18n import t
from app.core.security import sha256_hex
from app.core.utils import utcnow
from app.integrations import channels
from app.models.business import BusinessMember
from app.models.enums import Channel, MemberStatus, OutboxStatus
from app.models.identity import User
from app.models.system import Notification, NotificationDelivery, NotificationPreference, PushSubscription

log = logging.getLogger("wesal.notifications")

# event -> default external channels (in-app is always on)
EVENTS: dict[str, set[Channel]] = {
    "account_registered": {Channel.email},
    "account_verified": {Channel.email, Channel.sms},
    "account_rejected": {Channel.email},
    "team_invite": {Channel.email},
    "authorization_requested": {Channel.email, Channel.push},
    "authorization_issued": {Channel.email, Channel.sms, Channel.push},
    "authorization_activated": {Channel.email, Channel.push},
    "authorization_declined": {Channel.email},
    "authorization_expiring": {Channel.email, Channel.sms},
    "authorization_status_changed": {Channel.email, Channel.push},
    "order_new": {Channel.email, Channel.push},
    "order_approval_required": {Channel.email, Channel.sms, Channel.push, Channel.whatsapp},
    "order_approved": {Channel.email, Channel.push},
    "order_offer": {Channel.email, Channel.sms, Channel.push},
    "order_updated": {Channel.push},
    "order_changes_requested": {Channel.email, Channel.push},
    "order_preparing": {Channel.push},
    "order_out_for_delivery": {Channel.sms, Channel.push, Channel.whatsapp},
    "order_delivered": {Channel.email, Channel.push},
    "order_completed": {Channel.push},
    "order_rejected": {Channel.email, Channel.push},
    "order_cancelled": {Channel.email, Channel.push},
    "commission_updated": {Channel.push},
    "commission_paid": {Channel.email, Channel.push},
    "dispute_new": {Channel.email, Channel.push},
    "complaint_new": {Channel.email},
    "complaint_reply": {Channel.email, Channel.push},
    "return_requested": {Channel.email, Channel.push},
    "return_decided": {Channel.email, Channel.push},
    "task_assigned": {Channel.push},
    "rating_received": {Channel.push},
    "document_reviewed": {Channel.email},
}

MAX_ATTEMPTS = 5


def render(event: str, locale: str, params: dict) -> tuple[str, str]:
    return t(f"notifications.{event}.title", locale, **params), t(f"notifications.{event}.body", locale, **params)


def _prefs(db: Session, user_id: uuid.UUID, event: str) -> dict[Channel, bool]:
    rows = db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user_id,
                                                           NotificationPreference.event.in_([event, "*"]))).all()
    out: dict[Channel, bool] = {}
    for r in sorted(rows, key=lambda r: r.event != "*"):  # wildcard first, specific overrides
        out[r.channel] = r.enabled
    return out


def _target(db: Session, user: User, channel: Channel) -> list[str]:
    if channel == Channel.email:
        return [user.email] if user.email and user.email_verified_at else []
    if channel in (Channel.sms, Channel.whatsapp):
        return [user.phone] if user.phone and user.phone_verified_at else []
    if channel == Channel.push:
        subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user.id)).all()
        import json

        return [json.dumps({"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}) for s in subs]
    return []


def notify(
    db: Session,
    user_ids: Iterable[uuid.UUID],
    event: str,
    params: dict | None = None,
    *,
    link: str | None = None,
    entity_type: str | None = None,
    entity_id=None,
    dedupe_key: str | None = None,
    exclude_user_id: uuid.UUID | None = None,
) -> int:
    params = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in (params or {}).items()}
    defaults = EVENTS.get(event, set())
    count = 0
    with system_context(db):
        for uid in dict.fromkeys(user_ids):
            if uid is None or uid == exclude_user_id:
                continue
            user = db.get(User, uid)
            if user is None:
                continue
            stmt = insert(Notification).values(
                id=uuid.uuid4(), user_id=uid, event=event, params=params, link=link, entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None, dedupe_key=dedupe_key,
            )
            if dedupe_key:
                stmt = stmt.on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"],
                                                   index_where=Notification.dedupe_key.isnot(None))
            res = db.execute(stmt.returning(Notification.id))
            notif_id = res.scalar()
            if notif_id is None:  # duplicate
                continue
            count += 1
            prefs = _prefs(db, uid, event)
            for channel in Channel:
                if channel == Channel.in_app:
                    continue
                enabled = prefs.get(channel, channel in defaults)
                if not enabled or not channels.channel_enabled(channel.value):
                    continue
                for target in _target(db, user, channel):
                    db.execute(
                        insert(NotificationDelivery).values(
                            id=uuid.uuid4(), notification_id=notif_id, user_id=uid, channel=channel, target=target,
                            template=event, locale=user.locale, payload={"params": params, "link": link},
                            dedupe_key=f"{notif_id}:{channel.value}:{sha256_hex(target)[:16]}",
                        ).on_conflict_do_nothing()
                    )
    return count


def send_direct(db: Session, channel: Channel, target: str, template: str, locale: str, params: dict,
                *, user_id=None, dedupe_key: str | None = None) -> None:
    """Enqueue a direct message (OTP, password reset, invitation) not tied to an in-app notification."""
    with system_context(db):
        db.execute(
            insert(NotificationDelivery).values(
                id=uuid.uuid4(), user_id=user_id, channel=channel, target=target, template=template, locale=locale,
                payload={"params": params}, dedupe_key=dedupe_key,
            ).on_conflict_do_nothing()
        )


def members_with_permission(db: Session, business_id: uuid.UUID, perm: str | None = None) -> list[uuid.UUID]:
    with system_context(db):
        members = db.scalars(select(BusinessMember).where(BusinessMember.business_id == business_id,
                                                          BusinessMember.status == MemberStatus.active)).all()
        return [m.user_id for m in members if perm is None or perm in m.role.permission_codes]


def deliver_pending(db: Session, limit: int = 50) -> int:
    """Deliver due outbox rows. Uses SKIP LOCKED so several workers can run concurrently."""
    now = utcnow()
    rows = db.scalars(
        select(NotificationDelivery)
        .where(NotificationDelivery.status == OutboxStatus.pending, NotificationDelivery.next_attempt_at <= now)
        .order_by(NotificationDelivery.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    done = 0
    for row in rows:
        provider = channels.provider_for(row.channel.value)
        if provider is None:
            row.status = OutboxStatus.skipped
            row.last_error = "channel disabled"
            continue
        params = row.payload.get("params", {})
        if row.template.startswith("direct."):
            subject = t(f"messages.{row.template[7:]}.subject", row.locale, **params)
            body = t(f"messages.{row.template[7:]}.body", row.locale, **params)
        else:
            subject, body = render(row.template, row.locale, params)
        try:
            ref = provider.send(row.target or "", subject, body, {**row.payload, "locale": row.locale})
            row.status = OutboxStatus.sent
            row.sent_at = utcnow()
            row.provider_ref = ref
            done += 1
        except Exception as exc:  # noqa: BLE001
            row.attempts += 1
            row.last_error = str(exc)[:500]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = OutboxStatus.failed
            else:
                row.next_attempt_at = utcnow() + timedelta(seconds=30 * (2 ** row.attempts))
            log.warning("delivery %s via %s failed: %s", row.id, row.channel, exc)
    db.commit()
    return done
