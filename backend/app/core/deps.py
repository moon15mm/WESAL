"""Authentication & authorization dependencies.

Every protected endpoint resolves a *context*:
- ``Principal``           – an authenticated user.
- ``BusinessCtx``         – the user acting for a specific retailer/supplier business
                            (membership + permission verified server-side).
- ``RepCtx``              – the user acting as a sales representative.
- ``AdminCtx``            – a platform administrator (permission + MFA verified).

Business ids sent by clients (``X-Business-Id``) are only a *selector*: access is
granted exclusively through an active membership row.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit_denied
from app.core.config import settings
from app.core.db import get_db, set_rls_context
from app.core.errors import Forbidden, Unauthorized
from app.core.i18n import normalize_locale
from app.core.security import constant_time_equals, token_hash
from app.core.utils import utcnow
from app.models.business import Business, BusinessMember
from app.models.enums import BusinessStatus, BusinessType, MemberStatus, UserStatus, VerificationStatus
from app.models.identity import UserRole, UserSession
from app.models.reps import Representative

SESSION_COOKIE = "wesal_session"
CSRF_COOKIE = "wesal_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MFA_PENDING_ALLOWED = {"/api/v1/auth/mfa/verify", "/api/v1/auth/logout", "/api/v1/auth/me"}


@dataclass
class Principal:
    user: "object"
    session: UserSession
    locale: str
    platform_perms: set[str] = field(default_factory=set)
    platform_roles: set[str] = field(default_factory=set)
    rep: Representative | None = None
    memberships: list[BusinessMember] = field(default_factory=list)
    via_cookie: bool = True

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    def business_ids(self) -> list[uuid.UUID]:
        return [m.business_id for m in self.memberships]


@dataclass
class BusinessCtx:
    principal: Principal
    business: Business
    member: BusinessMember
    perms: set[str]

    @property
    def user(self):
        return self.principal.user

    @property
    def business_id(self) -> uuid.UUID:
        return self.business.id

    def has(self, perm: str) -> bool:
        return perm in self.perms

    def require(self, perm: str) -> None:
        if perm not in self.perms:
            raise Forbidden("permission_denied", params={"permission": perm})


@dataclass
class RepCtx:
    principal: Principal
    rep: Representative

    @property
    def user(self):
        return self.principal.user


@dataclass
class AdminCtx:
    principal: Principal
    perms: set[str]

    @property
    def user(self):
        return self.principal.user

    def require(self, perm: str) -> None:
        if perm not in self.perms:
            raise Forbidden("permission_denied", params={"permission": perm})


def request_locale(request: Request) -> str:
    return normalize_locale(request.headers.get("x-locale") or request.headers.get("accept-language"))


def _extract_token(request: Request) -> tuple[str | None, bool]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), False
    return request.cookies.get(SESSION_COOKIE), True


def _check_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise Forbidden("csrf_failed")


def load_principal(request: Request, db: Session) -> Principal | None:
    token, via_cookie = _extract_token(request)
    if not token:
        return None
    if via_cookie:
        _check_csrf(request)
    now = utcnow()
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_hash(token)))
    if sess is None or sess.revoked_at is not None or sess.expires_at <= now:
        return None
    if sess.last_seen_at + timedelta(minutes=settings.session_idle_minutes) <= now:
        sess.revoked_at = now
        db.commit()
        return None
    user = sess.user
    if user.status not in (UserStatus.active, UserStatus.pending):
        return None
    if sess.mfa_pending and request.url.path not in MFA_PENDING_ALLOWED:
        raise Unauthorized("mfa_required")
    if (now - sess.last_seen_at) > timedelta(minutes=5):
        sess.last_seen_at = now
        db.commit()

    roles = db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all()
    platform_perms: set[str] = set()
    for ur in roles:
        platform_perms |= ur.role.permission_codes
    memberships = list(
        db.scalars(
            select(BusinessMember).where(BusinessMember.user_id == user.id, BusinessMember.status == MemberStatus.active)
        ).all()
    )
    rep = db.scalar(select(Representative).where(Representative.user_id == user.id))
    principal = Principal(
        user=user,
        session=sess,
        locale=normalize_locale(request.headers.get("x-locale") or user.locale),
        platform_perms=platform_perms,
        platform_roles={ur.role.code for ur in roles},
        rep=rep,
        memberships=memberships,
        via_cookie=via_cookie,
    )
    set_rls_context(db, user_id=user.id, business_ids=principal.business_ids(), rep_id=rep.id if rep else None)
    request.state.user_id = user.id
    return principal


def optional_principal(request: Request, db: Session = Depends(get_db)) -> Principal | None:
    return load_principal(request, db)


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    principal = load_principal(request, db)
    if principal is None:
        raise Unauthorized()
    return principal


def _business_ctx(request: Request, db: Session, principal: Principal, btype: BusinessType, perm: str | None) -> BusinessCtx:
    selector = request.headers.get("x-business-id")
    candidates = [m for m in principal.memberships if m.business.type == btype]
    member: BusinessMember | None = None
    if selector:
        try:
            wanted = uuid.UUID(selector)
        except ValueError:
            raise Forbidden("invalid_business_context")
        member = next((m for m in candidates if m.business_id == wanted), None)
        if member is None:
            audit_denied("access.business_context", actor_user_id=principal.id, entity_type="business",
                         entity_id=selector, reason="no membership", request=request)
            raise Forbidden("not_a_member")
    elif len(candidates) == 1:
        member = candidates[0]
    elif not candidates:
        raise Forbidden("no_business_context", params={"type": btype.value})
    else:
        raise Forbidden("business_context_required")

    business = member.business
    if business.status != BusinessStatus.active:
        raise Forbidden("business_suspended")
    perms = member.role.permission_codes
    if perm and perm not in perms:
        audit_denied("access.permission", actor_user_id=principal.id, entity_type="business",
                     entity_id=business.id, reason=f"missing {perm}", request=request)
        raise Forbidden("permission_denied", params={"permission": perm})
    # narrow row-level security to this single business
    set_rls_context(db, user_id=principal.id, business_ids=[business.id])
    return BusinessCtx(principal=principal, business=business, member=member, perms=perms)


def retailer_ctx(perm: str | None = None):
    def dep(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)) -> BusinessCtx:
        return _business_ctx(request, db, principal, BusinessType.retailer, perm)

    return dep


def supplier_ctx(perm: str | None = None):
    def dep(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)) -> BusinessCtx:
        return _business_ctx(request, db, principal, BusinessType.supplier, perm)

    return dep


def rep_ctx(require_verified: bool = False):
    def dep(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)) -> RepCtx:
        rep = principal.rep
        if rep is None:
            raise Forbidden("not_a_representative")
        if not rep.is_active:
            raise Forbidden("representative_inactive")
        if require_verified and rep.verification_status != VerificationStatus.verified:
            raise Forbidden("representative_not_verified")
        set_rls_context(db, user_id=principal.id, rep_id=rep.id)
        return RepCtx(principal=principal, rep=rep)

    return dep


def admin_ctx(perm: str | None = None):
    def dep(request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)) -> AdminCtx:
        if not principal.platform_perms:
            audit_denied("access.admin", actor_user_id=principal.id, reason="not admin", request=request)
            raise Forbidden("admin_only")
        if settings.mfa_enforce_admin and not (principal.user.mfa_enabled and principal.session.mfa_verified):
            raise Forbidden("mfa_setup_required")
        if perm and perm not in principal.platform_perms:
            audit_denied("access.admin_permission", actor_user_id=principal.id, reason=f"missing {perm}", request=request)
            raise Forbidden("permission_denied", params={"permission": perm})
        set_rls_context(db, user_id=principal.id, bypass=True)
        return AdminCtx(principal=principal, perms=principal.platform_perms)

    return dep
