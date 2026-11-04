"""Periodic jobs (single instance).

    python -m app.workers.scheduler          # loop forever
    python -m app.workers.scheduler --once   # run every job once (cron / tests)
"""
from __future__ import annotations

import argparse
import logging
import signal
import time
from datetime import timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.db import system_session
from app.core.utils import utcnow
from app.models.enums import AuthorizationStatus, OfferStatus, OrderStatus, VisitStatus
from app.models.identity import UserSession, VerificationCode
from app.models.orders import Order, OrderOffer
from app.models.crm import Visit
from app.models.reps import Authorization
from app.models.system import JobRun

log = logging.getLogger("wesal.scheduler")


def expire_authorizations(db) -> int:
    from app.modules.authorizations.service import transition

    today = utcnow().date()
    n = 0
    for a in db.scalars(select(Authorization).where(Authorization.status.in_([AuthorizationStatus.active, AuthorizationStatus.suspended]),
                                                    Authorization.end_date.isnot(None), Authorization.end_date < today)):
        transition(db, a, AuthorizationStatus.expired, None, "expired", "end date passed")
        n += 1
    return n


def warn_expiring_authorizations(db) -> int:
    from app.modules.notifications.service import members_with_permission, notify

    today = utcnow().date()
    horizon = today + timedelta(days=settings.authorization_expiry_warning_days)
    n = 0
    for a in db.scalars(select(Authorization).where(Authorization.status == AuthorizationStatus.active,
                                                    Authorization.end_date.isnot(None), Authorization.end_date <= horizon,
                                                    Authorization.expiry_warned_at.is_(None))):
        params = {"number": a.number, "date": a.end_date.isoformat(), "supplier": a.supplier.trade_name_ar,
                  "representative": a.representative.display_name}
        notify(db, [a.representative.user_id], "authorization_expiring", params, link=f"/app/rep/authorizations/{a.id}",
               dedupe_key=f"auth-expiring:{a.id}:{a.end_date}")
        notify(db, members_with_permission(db, a.supplier_id, "supplier.reps.manage"), "authorization_expiring", params,
               link=f"/app/supplier/authorizations/{a.id}", dedupe_key=f"auth-expiring:{a.id}:{a.end_date}")
        a.expiry_warned_at = utcnow()
        n += 1
    return n


def auto_complete_orders(db) -> int:
    """Delivered orders without the store's confirmation complete after N days (store can still dispute/return)."""
    from app.modules.commissions import service as commissions
    from app.modules.orders import service as svc

    cutoff = utcnow() - timedelta(days=settings.auto_complete_days)
    n = 0
    for o in db.scalars(select(Order).where(Order.status == OrderStatus.delivered, Order.delivered_at <= cutoff)):
        svc.transition(db, o, OrderStatus.completed, None, "system", "auto-completed: no response from store")
        commissions.on_order_event(db, o, "completed")
        n += 1
    return n


def release_commissions(db) -> int:
    from app.modules.commissions.service import release_due

    return release_due(db)


def expire_offers(db) -> int:
    n = 0
    for f in db.scalars(select(OrderOffer).where(OrderOffer.status == OfferStatus.pending, OrderOffer.valid_until.isnot(None),
                                                 OrderOffer.valid_until < utcnow())):
        f.status = OfferStatus.expired
        n += 1
    return n


def mark_missed_visits(db) -> int:
    n = 0
    for v in db.scalars(select(Visit).where(Visit.status == VisitStatus.scheduled, Visit.scheduled_at < utcnow() - timedelta(days=1))):
        v.status = VisitStatus.missed
        n += 1
    return n


def retention_cleanup(db) -> int:
    """Data minimisation, as published in the data-retention policy:
    verification codes 7 days after expiry, sessions 90 days after expiry, in-app notifications
    after 12 months, sent/failed outbox deliveries after 90 days, contact messages after 24 months,
    and visit GPS coordinates after 24 months (the visit record itself is kept)."""
    from sqlalchemy import update

    from app.models.crm import Visit
    from app.models.enums import OutboxStatus
    from app.models.system import ContactMessage, Notification, NotificationDelivery

    now = utcnow()
    n = 0
    n += db.execute(delete(VerificationCode).where(VerificationCode.expires_at < now - timedelta(days=7))).rowcount or 0
    n += db.execute(delete(UserSession).where(UserSession.expires_at < now - timedelta(days=90))).rowcount or 0
    n += db.execute(delete(Notification).where(Notification.created_at < now - timedelta(days=365))).rowcount or 0
    n += db.execute(delete(NotificationDelivery).where(NotificationDelivery.status.in_([OutboxStatus.sent, OutboxStatus.failed, OutboxStatus.skipped]),
                                                       NotificationDelivery.created_at < now - timedelta(days=90))).rowcount or 0
    n += db.execute(delete(ContactMessage).where(ContactMessage.created_at < now - timedelta(days=730))).rowcount or 0
    n += db.execute(update(Visit).where(Visit.created_at < now - timedelta(days=730), Visit.start_lat.is_not(None))
                    .values(start_lat=None, start_lng=None, end_lat=None, end_lng=None)).rowcount or 0
    return n


JOBS = [
    ("expire_authorizations", expire_authorizations, 3600),
    ("warn_expiring_authorizations", warn_expiring_authorizations, 3600 * 6),
    ("auto_complete_orders", auto_complete_orders, 3600),
    ("release_commissions", release_commissions, 3600),
    ("expire_offers", expire_offers, 900),
    ("mark_missed_visits", mark_missed_visits, 3600 * 3),
    ("retention_cleanup", retention_cleanup, 3600 * 24),
]


def run_job(name, fn) -> int:
    with system_session() as db:
        run = JobRun(job=name)
        db.add(run)
        db.commit()
        try:
            n = fn(db)
            run.processed, run.success, run.finished_at = n or 0, True, utcnow()
            db.commit()
            return n or 0
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log.exception("job %s failed", name)
            run = db.get(JobRun, run.id)
            run.success, run.error, run.finished_at = False, str(exc)[:2000], utcnow()
            db.commit()
            return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        for name, fn, _ in JOBS:
            print(name, run_job(name, fn))
        return
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    last: dict[str, float] = {}
    while running:
        now = time.time()
        for name, fn, every in JOBS:
            if now - last.get(name, 0) >= every:
                run_job(name, fn)
                last[name] = now
        time.sleep(30)


if __name__ == "__main__":
    from app.main import configure_logging

    configure_logging()
    main()
