from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import CSRF_COOKIE, SESSION_COOKIE, Principal, current_principal
from app.core.errors import NotFound, Unauthorized, ValidationFailed
from app.core.i18n import SUPPORTED_LOCALES, localized
from app.core.security import (
    decrypt_field,
    encrypt_field,
    hash_password,
    new_numeric_code,
    new_token,
    new_totp_secret,
    token_hash,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.core.utils import mask_email, mask_phone, normalize_phone, utcnow
from app.models.enums import Channel, UserStatus, VerificationPurpose
from app.models.identity import User, UserSession
from app.modules.auth import service

router = APIRouter(prefix="/auth", tags=["auth"])

Locale = Literal["ar", "en", "ur", "hi"]


class RegisterIn(BaseModel):
    account_type: Literal["retailer", "supplier", "representative"]
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=1, max_length=128)
    locale: Locale = "ar"
    accept_terms: bool
    business_name_ar: str | None = Field(default=None, max_length=200)
    business_name_en: str | None = Field(default=None, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    cr_number: str | None = Field(default=None, pattern=r"^\d{10}$")
    vat_number: str | None = Field(default=None, pattern=r"^3\d{13}3$")
    city_id: int | None = None
    district: str | None = Field(default=None, max_length=120)
    address_line: str | None = Field(default=None, max_length=255)
    branch_name: str | None = Field(default=None, max_length=160)
    store_type: str | None = Field(default=None, max_length=40)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class LoginIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=64)


class VerifyRequestIn(BaseModel):
    channel: Literal["email", "sms"]


class VerifyConfirmIn(BaseModel):
    channel: Literal["email", "sms"]
    code: str = Field(min_length=4, max_length=12)


class ForgotIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)


class ResetIn(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=64)
    new_password: str = Field(min_length=1, max_length=128)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=1, max_length=128)


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)


class OtpLoginIn(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=6, max_length=6)


class MfaDisableIn(BaseModel):
    password: str
    code: str


class ProfileIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    locale: Locale | None = None
    document_locale: Locale | None = None
    number_system: Literal["latn", "arab"] | None = None
    timezone: str | None = Field(default=None, max_length=64)
    currency: Literal["SAR", "USD", "AED", "KWD", "BHD", "QAR", "OMR", "EGP", "PKR", "INR"] | None = None


def _client_key(request: Request) -> str:
    return getattr(request.state, "client_ip", "unknown")


def _set_session_cookies(response: Response, token: str, expires: datetime) -> None:
    max_age = int((expires - utcnow()).total_seconds())
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=settings.cookie_secure,
                        samesite="lax", domain=settings.cookie_domain, path="/")
    response.set_cookie(CSRF_COOKIE, new_token(16), max_age=max_age, httponly=False, secure=settings.cookie_secure,
                        samesite="lax", domain=settings.cookie_domain, path="/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, domain=settings.cookie_domain, path="/")
    response.delete_cookie(CSRF_COOKIE, domain=settings.cookie_domain, path="/")


def _session_response(request: Request, response: Response, sess: UserSession, token: str, **extra) -> dict:
    _set_session_cookies(response, token, sess.expires_at)
    out = {"ok": True, **extra}
    if request.headers.get("x-auth-mode") == "bearer":
        out["session_token"] = token
    return out


def me_payload(db: Session, principal: Principal) -> dict:
    u = principal.user
    memberships = []
    for m in principal.memberships:
        b = m.business
        memberships.append({
            "business_id": str(b.id), "type": b.type.value, "name": b.display_name(principal.locale),
            "trade_name_ar": b.trade_name_ar, "trade_name_en": b.trade_name_en,
            "verification_status": b.verification_status.value, "status": b.status.value,
            "role": m.role.code, "role_name": localized(m.role.name, principal.locale),
            "permissions": sorted(m.role.permission_codes), "branch_id": str(m.branch_id) if m.branch_id else None,
        })
    rep = principal.rep
    return {
        "id": str(u.id), "full_name": u.full_name, "email": u.email, "phone": u.phone, "locale": u.locale,
        "document_locale": u.document_locale or u.locale, "number_system": u.number_system, "timezone": u.timezone,
        "currency": u.currency, "status": u.status.value,
        "email_verified": u.email_verified_at is not None, "phone_verified": u.phone_verified_at is not None,
        "mfa_enabled": u.mfa_enabled, "mfa_verified": principal.session.mfa_verified,
        "mfa_pending": principal.session.mfa_pending,
        "platform_roles": sorted(principal.platform_roles), "platform_permissions": sorted(principal.platform_perms),
        "mfa_required_for_admin": settings.mfa_enforce_admin,
        "memberships": memberships,
        "representative": None if rep is None else {
            "id": str(rep.id), "kind": rep.kind.value, "verification_status": rep.verification_status.value,
            "display_name": rep.display_name, "is_active": rep.is_active,
        },
    }


@router.get("/csrf")
def csrf(response: Response):
    token = new_token(16)
    response.set_cookie(CSRF_COOKIE, token, httponly=False, secure=settings.cookie_secure, samesite="lax",
                        domain=settings.cookie_domain, path="/")
    return {"csrf": token}


@router.post("/register", status_code=201)
def register(data: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.hit(f"register:{_client_key(request)}", 10, 3600)
    user = service.register(db, data, request)
    sess, token = service.create_session(db, user, request)
    db.commit()
    return _session_response(request, response, sess, token, user_id=str(user.id))


@router.post("/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.hit(f"login-ip:{_client_key(request)}", 30, 300)
    ratelimit.hit(f"login-id:{data.identifier.lower()}", 10, 300)
    user = service.authenticate(db, data.identifier, data.password, request)
    sess, token = service.create_session(db, user, request, mfa_pending=user.mfa_enabled)
    audit(db, "auth.login", actor_user_id=user.id, entity_type="session", entity_id=sess.id, request=request)
    db.commit()
    return _session_response(request, response, sess, token, mfa_required=user.mfa_enabled)


@router.post("/otp/request")
def otp_request(data: OtpRequestIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.hit(f"otp-ip:{_client_key(request)}", 10, 3600)
    phone = normalize_phone(data.phone)
    if not phone:
        raise ValidationFailed("invalid_phone")
    from app.integrations.channels import channel_enabled

    if not channel_enabled("sms"):
        raise ValidationFailed("sms_not_configured", status_code=503)
    user = db.scalar(select(User).where(User.phone == phone, User.status == UserStatus.active))
    if user and user.phone_verified_at:
        service.issue_code(db, user, Channel.sms, VerificationPurpose.login_otp)
        db.commit()
    return {"ok": True}  # no account enumeration


@router.post("/otp/login")
def otp_login(data: OtpLoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ratelimit.hit(f"otp-login:{_client_key(request)}", 20, 3600)
    phone = normalize_phone(data.phone)
    user = db.scalar(select(User).where(User.phone == phone)) if phone else None
    if user is None or user.status != UserStatus.active:
        raise Unauthorized("invalid_credentials")
    service.consume_code(db, phone, VerificationPurpose.login_otp, data.code)
    sess, token = service.create_session(db, user, request, mfa_pending=user.mfa_enabled)
    audit(db, "auth.login_otp", actor_user_id=user.id, request=request)
    db.commit()
    return _session_response(request, response, sess, token, mfa_required=user.mfa_enabled)


@router.post("/mfa/verify")
def mfa_verify(data: CodeIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    ratelimit.hit(f"mfa:{principal.id}", 10, 300)
    user = principal.user
    sess = principal.session
    secret = decrypt_field(user.mfa_secret_enc) if user.mfa_secret_enc else None
    ok = bool(secret and verify_totp(secret, data.code))
    if not ok and user.mfa_recovery_hashes:
        h = token_hash(data.code.strip().upper())
        if h in user.mfa_recovery_hashes:
            user.mfa_recovery_hashes = [x for x in user.mfa_recovery_hashes if x != h]
            ok = True
    if not ok:
        audit(db, "auth.mfa_verify", actor_user_id=user.id, result="denied", request=request)
        db.commit()
        raise Unauthorized("mfa_invalid")
    sess.mfa_pending = False
    sess.mfa_verified = True
    audit(db, "auth.mfa_verify", actor_user_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/mfa/setup")
def mfa_setup(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    user = principal.user
    if user.mfa_enabled:
        raise ValidationFailed("mfa_already_enabled")
    secret = new_totp_secret()
    user.mfa_secret_enc = encrypt_field(secret)
    db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.email or user.phone or str(user.id))}


@router.post("/mfa/enable")
def mfa_enable(data: CodeIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    user = principal.user
    secret = decrypt_field(user.mfa_secret_enc) if user.mfa_secret_enc else None
    if not secret or not verify_totp(secret, data.code):
        raise ValidationFailed("mfa_invalid")
    codes = [f"{new_numeric_code(4)}-{new_numeric_code(4)}" for _ in range(8)]
    user.mfa_recovery_hashes = [token_hash(c) for c in codes]
    user.mfa_enabled = True
    principal.session.mfa_verified = True
    audit(db, "auth.mfa_enable", actor_user_id=user.id, request=request)
    db.commit()
    return {"recovery_codes": codes}


@router.post("/mfa/disable")
def mfa_disable(data: MfaDisableIn, request: Request, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    user = principal.user
    secret = decrypt_field(user.mfa_secret_enc) if user.mfa_secret_enc else None
    if not verify_password(data.password, user.password_hash) or not secret or not verify_totp(secret, data.code):
        raise Unauthorized("invalid_credentials")
    user.mfa_enabled = False
    user.mfa_secret_enc = None
    user.mfa_recovery_hashes = None
    audit(db, "auth.mfa_disable", actor_user_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(response: Response, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    principal.session.revoked_at = utcnow()
    db.commit()
    _clear_cookies(response)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(request: Request, response: Response, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    n = service.revoke_all_sessions(db, principal.id)
    audit(db, "auth.logout_all", actor_user_id=principal.id, changes={"revoked": n}, request=request)
    db.commit()
    _clear_cookies(response)
    return {"ok": True, "revoked": n}


@router.get("/me")
def me(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    return me_payload(db, principal)


@router.patch("/me")
def update_me(data: ProfileIn, db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    user = principal.user
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "timezone":
            from zoneinfo import available_timezones

            if v not in available_timezones():
                raise ValidationFailed("invalid_timezone", fields={"timezone": "invalid"})
        setattr(user, k, v.strip() if isinstance(v, str) and k == "full_name" else v)
    db.commit()
    return me_payload(db, principal)


@router.get("/sessions")
def sessions(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == principal.id, UserSession.revoked_at.is_(None),
                                                UserSession.expires_at > utcnow()).order_by(UserSession.last_seen_at.desc())).all()
    return [{"id": str(s.id), "created_at": s.created_at, "last_seen_at": s.last_seen_at, "ip": s.ip,
             "user_agent": s.user_agent, "current": s.id == principal.session.id} for s in rows]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)):
    s = db.get(UserSession, session_id)
    if s is None or s.user_id != principal.id:
        raise NotFound()
    s.revoked_at = utcnow()
    audit(db, "auth.session_revoke", actor_user_id=principal.id, entity_type="session", entity_id=s.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/verify/request")
def verify_request(data: VerifyRequestIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)):
    ratelimit.hit(f"verify:{principal.id}", 5, 900)
    user = principal.user
    if data.channel == "email":
        if not user.email or user.email_verified_at:
            raise ValidationFailed("nothing_to_verify")
        service.issue_code(db, user, Channel.email, VerificationPurpose.verify_email)
    else:
        if not user.phone or user.phone_verified_at:
            raise ValidationFailed("nothing_to_verify")
        service.issue_code(db, user, Channel.sms, VerificationPurpose.verify_phone)
    db.commit()
    return {"ok": True, "target": mask_email(user.email) if data.channel == "email" else mask_phone(user.phone)}


@router.post("/verify/confirm")
def verify_confirm(data: VerifyConfirmIn, request: Request, db: Session = Depends(get_db),
                   principal: Principal = Depends(current_principal)):
    ratelimit.hit(f"verify-confirm:{principal.id}", 15, 900)
    user = principal.user
    if data.channel == "email":
        service.consume_code(db, user.email or "", VerificationPurpose.verify_email, data.code)
        user.email_verified_at = utcnow()
    else:
        service.consume_code(db, user.phone or "", VerificationPurpose.verify_phone, data.code)
        user.phone_verified_at = utcnow()
    audit(db, f"auth.verify_{data.channel}", actor_user_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/password/forgot")
def forgot(data: ForgotIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.hit(f"forgot-ip:{_client_key(request)}", 10, 3600)
    user = service.find_user(db, data.identifier)
    if user and user.status in (UserStatus.active, UserStatus.pending):
        try:
            if "@" in data.identifier:
                service.issue_code(db, user, Channel.email, VerificationPurpose.reset_password)
            else:
                service.issue_code(db, user, Channel.sms, VerificationPurpose.reset_password)
            db.commit()
        except Exception:  # never reveal whether the account exists
            db.rollback()
    return {"ok": True}


@router.post("/password/reset")
def reset(data: ResetIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.hit(f"reset-ip:{_client_key(request)}", 20, 3600)
    user = service.find_user(db, data.identifier)
    if user is None:
        raise ValidationFailed("code_invalid")
    target = user.email if "@" in data.identifier else user.phone
    service.consume_code(db, target or "", VerificationPurpose.reset_password, data.code)
    service.validate_password(data.new_password, user.email, user.phone)
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = utcnow()
    user.failed_login_count = 0
    user.locked_until = None
    if user.status == UserStatus.pending:  # invited member setting first password
        user.status = UserStatus.active
    if "@" in data.identifier and not user.email_verified_at:
        user.email_verified_at = utcnow()  # possession of the emailed token proves the address
    service.revoke_all_sessions(db, user.id)
    audit(db, "auth.password_reset", actor_user_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/password/change")
def change_password(data: ChangePasswordIn, request: Request, db: Session = Depends(get_db),
                    principal: Principal = Depends(current_principal)):
    user = principal.user
    if not verify_password(data.current_password, user.password_hash):
        raise Unauthorized("invalid_credentials")
    service.validate_password(data.new_password, user.email, user.phone)
    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = utcnow()
    service.revoke_all_sessions(db, user.id, except_id=principal.session.id)
    audit(db, "auth.password_change", actor_user_id=user.id, request=request)
    db.commit()
    return {"ok": True}


@router.get("/locales")
def locales():
    return {"supported": list(SUPPORTED_LOCALES)}
