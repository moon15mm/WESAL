"""PDPL helpers: personal data export and anonymization (deletion requests).

Commercial records (orders, invoices, commissions, audit logs) are retained for the
statutory period; the person's identifying data on the account is anonymized."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import system_context
from app.core.security import hash_password, new_token
from app.core.utils import utcnow
from app.models.business import BusinessMember
from app.models.enums import MemberStatus, UserStatus
from app.models.identity import User, UserSession
from app.models.reps import Representative
from app.models.system import Notification, PushSubscription


def export_user_data(db: Session, user: User) -> dict:
    with system_context(db):
        members = db.scalars(select(BusinessMember).where(BusinessMember.user_id == user.id)).all()
        rep = db.scalar(select(Representative).where(Representative.user_id == user.id))
        sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()
        notes = db.scalars(select(Notification).where(Notification.user_id == user.id).limit(1000)).all()
    return {
        "generated_at": utcnow().isoformat(),
        "account": {"id": str(user.id), "full_name": user.full_name, "email": user.email, "phone": user.phone,
                    "locale": user.locale, "timezone": user.timezone, "created_at": user.created_at.isoformat(),
                    "terms_version": user.terms_version,
                    "terms_accepted_at": user.terms_accepted_at.isoformat() if user.terms_accepted_at else None},
        "memberships": [{"business": m.business.trade_name_ar, "role": m.role.code, "status": m.status.value} for m in members],
        "representative_profile": None if rep is None else {"display_name": rep.display_name, "headline": rep.headline, "bio": rep.bio,
                                                            "skills": rep.skills, "experience_years": rep.experience_years},
        "sessions": [{"created_at": s.created_at.isoformat(), "ip": s.ip, "user_agent": s.user_agent} for s in sessions],
        "notifications": [{"event": n.event, "created_at": n.created_at.isoformat()} for n in notes],
    }


def anonymize_user(db: Session, user_id: uuid.UUID) -> None:
    with system_context(db):
        u = db.get(User, user_id)
        if u is None:
            return
        tag = uuid.uuid4().hex[:10]
        u.full_name = f"Deleted user {tag}"
        u.email = None
        u.phone = None
        u.password_hash = hash_password(new_token(24))
        u.status = UserStatus.deleted
        u.mfa_enabled, u.mfa_secret_enc, u.mfa_recovery_hashes = False, None, None
        for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id)):
            s.revoked_at = s.revoked_at or utcnow()
            s.ip, s.user_agent = None, None
        for m in db.scalars(select(BusinessMember).where(BusinessMember.user_id == u.id)):
            m.status = MemberStatus.disabled
        for p in db.scalars(select(PushSubscription).where(PushSubscription.user_id == u.id)):
            db.delete(p)
        rep = db.scalar(select(Representative).where(Representative.user_id == u.id))
        if rep:
            rep.display_name, rep.bio, rep.headline, rep.public_profile, rep.is_active = u.full_name, None, None, False, False
