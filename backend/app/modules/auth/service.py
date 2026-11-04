from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import system_context
from app.core.errors import AppError, Conflict, RateLimited, Unauthorized, ValidationFailed
from app.core.rbac import OWNER_ROLE, SENSITIVE_ROLE_CODES
from app.core.security import (
    hash_password,
    needs_rehash,
    new_numeric_code,
    new_token,
    password_problems,
    token_hash,
    verify_password,
)
from app.core.utils import normalize_phone, slugify, utcnow
from app.models.business import Branch, Business, BusinessMember, City
from app.models.enums import (
    BusinessType,
    Channel,
    MemberStatus,
    RepKind,
    RoleScope,
    UserStatus,
    VerificationPurpose,
    VerificationStatus,
)
from app.models.identity import Role, User, UserRole, UserSession, VerificationCode
from app.models.reps import Representative, RepresentativeArea
from app.modules.notifications.service import notify, send_direct

TERMS_VERSION = "1.0"


def find_user(db: Session, identifier: str) -> User | None:
    identifier = (identifier or "").strip()
    if "@" in identifier:
        return db.scalar(select(User).where(func.lower(User.email) == identifier.lower()))
    phone = normalize_phone(identifier)
    if phone:
        return db.scalar(select(User).where(User.phone == phone))
    return None


def system_role(db: Session, code: str) -> Role:
    role = db.scalar(select(Role).where(Role.code == code, Role.business_id.is_(None)))
    if role is None:
        raise AppError("role_missing", status_code=500, params={"role": code})
    return role


def unique_slug(db: Session, base: str) -> str:
    slug = slugify(base)
    candidate, i = slug, 1
    while db.scalar(select(Business.id).where(Business.slug == candidate)):
        i += 1
        candidate = f"{slug}-{i}"
    return candidate


def validate_password(password: str, email: str | None, phone: str | None) -> None:
    problems = password_problems(password, email=email, phone=phone)
    if problems:
        raise ValidationFailed("weak_password", fields={"password": problems[0]})


def register(db: Session, data, request=None) -> User:
    if not data.accept_terms:
        raise ValidationFailed("terms_required", fields={"accept_terms": "required"})
    email = data.email.lower() if data.email else None
    phone = normalize_phone(data.phone) if data.phone else None
    if data.phone and not phone:
        raise ValidationFailed("invalid_phone", fields={"phone": "invalid"})
    if data.account_type in ("retailer", "representative") and not phone:
        raise ValidationFailed("phone_required", fields={"phone": "required"})
    if data.account_type == "supplier" and not email:
        raise ValidationFailed("email_required", fields={"email": "required"})
    if not email and not phone:
        raise ValidationFailed("identifier_required")
    validate_password(data.password, email, phone)
    if email and db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise Conflict("account_exists", fields={"email": "taken"})
    if phone and db.scalar(select(User.id).where(User.phone == phone)):
        raise Conflict("account_exists", fields={"phone": "taken"})
    if data.city_id is not None and db.get(City, data.city_id) is None:
        raise ValidationFailed("invalid_city", fields={"city_id": "invalid"})

    now = utcnow()
    user = User(
        email=email, phone=phone, password_hash=hash_password(data.password), full_name=data.full_name.strip(),
        status=UserStatus.active, locale=data.locale, terms_version=TERMS_VERSION, terms_accepted_at=now,
        password_changed_at=now,
    )
    db.add(user)
    db.flush()

    with system_context(db):
        if data.account_type in ("retailer", "supplier"):
            btype = BusinessType(data.account_type)
            if not data.business_name_ar:
                raise ValidationFailed("business_name_required", fields={"business_name_ar": "required"})
            if data.cr_number and db.scalar(select(Business.id).where(Business.cr_number == data.cr_number,
                                                                      Business.type == btype)):
                raise Conflict("business_exists", fields={"cr_number": "taken"})
            business = Business(
                type=btype, legal_name=data.legal_name or data.business_name_ar, trade_name_ar=data.business_name_ar,
                trade_name_en=data.business_name_en, slug=unique_slug(db, data.business_name_en or data.business_name_ar),
                cr_number=data.cr_number, vat_number=data.vat_number, vat_registered=bool(data.vat_number),
                city_id=data.city_id, email=email, phone=phone, store_type=data.store_type,
                verification_status=VerificationStatus.unverified, created_by=user.id,
            )
            db.add(business)
            db.flush()
            role = system_role(db, OWNER_ROLE[RoleScope(data.account_type)])
            db.add(BusinessMember(business_id=business.id, user_id=user.id, role_id=role.id, status=MemberStatus.active))
            if btype == BusinessType.retailer:
                db.add(Branch(business_id=business.id, name=data.branch_name or data.business_name_ar, code="MAIN",
                              city_id=data.city_id, district=data.district, address_line=data.address_line,
                              lat=data.lat, lng=data.lng, phone=phone, is_primary=True, manager_user_id=user.id))
        else:
            rep = Representative(user_id=user.id, kind=RepKind.independent, display_name=user.full_name,
                                 home_city_id=data.city_id, verification_status=VerificationStatus.unverified)
            db.add(rep)
            db.flush()
            if data.city_id:
                db.add(RepresentativeArea(representative_id=rep.id, city_id=data.city_id))
        audit(db, "auth.register", actor_user_id=user.id, entity_type="user", entity_id=user.id,
              changes={"account_type": data.account_type}, request=request)
        notify(db, [user.id], "account_registered", {"name": user.full_name}, link="/app")
    if email:
        issue_code(db, user, Channel.email, VerificationPurpose.verify_email)
    if phone:
        issue_code(db, user, Channel.sms, VerificationPurpose.verify_phone)
    return user


def issue_code(db: Session, user: User | None, channel: Channel, purpose: VerificationPurpose, *,
               target: str | None = None, reference_id: str | None = None, ttl_minutes: int | None = None) -> str:
    target = target or (user.email if channel == Channel.email else user.phone)
    if not target:
        raise ValidationFailed("no_target_for_channel")
    # at most 5 codes per target+purpose per hour
    since = utcnow() - timedelta(hours=1)
    recent = db.scalar(select(func.count()).select_from(VerificationCode).where(
        VerificationCode.target == target, VerificationCode.purpose == purpose, VerificationCode.created_at >= since))
    if recent and recent >= 5:
        raise RateLimited("too_many_codes")
    # invalidate previous active codes
    for old in db.scalars(select(VerificationCode).where(VerificationCode.target == target, VerificationCode.purpose == purpose,
                                                         VerificationCode.consumed_at.is_(None))):
        old.consumed_at = utcnow()
    long_token = purpose == VerificationPurpose.reset_password and channel == Channel.email
    code = new_token(24) if long_token else new_numeric_code(6)
    db.add(VerificationCode(
        user_id=user.id if user else None, purpose=purpose, channel=channel, target=target, code_hash=token_hash(code),
        reference_id=reference_id,
        expires_at=utcnow() + timedelta(minutes=ttl_minutes or (60 if long_token else settings.otp_ttl_minutes)),
    ))
    locale = user.locale if user else settings.default_locale
    params = {"code": code, "minutes": ttl_minutes or settings.otp_ttl_minutes}
    if long_token:
        params["link"] = f"{settings.app_base_url}/{locale}/reset-password?token={code}&email={target}"
    send_direct(db, channel, target, f"direct.{purpose.value}", locale, params, user_id=user.id if user else None)
    db.flush()
    return code


def consume_code(db: Session, target: str, purpose: VerificationPurpose, code: str, reference_id: str | None = None) -> VerificationCode:
    row = db.scalar(select(VerificationCode).where(
        VerificationCode.target == target, VerificationCode.purpose == purpose, VerificationCode.consumed_at.is_(None),
    ).order_by(VerificationCode.created_at.desc()).limit(1).with_for_update())
    if row is None or row.expires_at <= utcnow():
        raise ValidationFailed("code_invalid")
    if reference_id is not None and row.reference_id != reference_id:
        raise ValidationFailed("code_invalid")
    if row.attempts >= settings.otp_max_attempts:
        row.consumed_at = utcnow()
        db.commit()
        raise ValidationFailed("code_attempts_exceeded")
    if row.code_hash != token_hash((code or "").strip()):
        row.attempts += 1
        db.commit()
        raise ValidationFailed("code_invalid")
    row.consumed_at = utcnow()
    return row


def is_sensitive(db: Session, user: User) -> bool:
    codes = set(db.scalars(select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)))
    with system_context(db):
        codes |= set(db.scalars(select(Role.code).join(BusinessMember, BusinessMember.role_id == Role.id)
                                .where(BusinessMember.user_id == user.id, BusinessMember.status == MemberStatus.active)))
    return bool(codes & SENSITIVE_ROLE_CODES)


def create_session(db: Session, user: User, request, *, mfa_pending: bool = False) -> tuple[UserSession, str]:
    token = new_token(32)
    ttl = settings.sensitive_session_ttl_hours if is_sensitive(db, user) else settings.session_ttl_hours
    sess = UserSession(
        user_id=user.id, token_hash=token_hash(token), expires_at=utcnow() + timedelta(hours=ttl),
        mfa_pending=mfa_pending, mfa_verified=False,
        ip=getattr(request.state, "client_ip", None) if request else None,
        user_agent=(request.headers.get("user-agent") or "")[:400] if request else None,
    )
    db.add(sess)
    user.last_login_at = utcnow()
    db.flush()
    return sess, token


def authenticate(db: Session, identifier: str, password: str, request) -> User:
    user = find_user(db, identifier)
    now = utcnow()
    if user is not None and user.locked_until and user.locked_until > now:
        verify_password(password, None)  # equalize timing
        audit(db, "auth.login", actor_user_id=user.id, result="denied", reason="locked", request=request)
        db.commit()
        raise Unauthorized("account_locked", params={"minutes": settings.login_lock_minutes})
    ok = verify_password(password, user.password_hash if user else None)
    if not ok or user is None:
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=settings.login_lock_minutes)
                user.failed_login_count = 0
            audit(db, "auth.login", actor_user_id=user.id, result="denied", reason="bad password", request=request)
            db.commit()
        raise Unauthorized("invalid_credentials")
    if user.status == UserStatus.suspended:
        raise Unauthorized("account_suspended")
    if user.status == UserStatus.deleted:
        raise Unauthorized("invalid_credentials")
    user.failed_login_count = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def revoke_all_sessions(db: Session, user_id: uuid.UUID, except_id: uuid.UUID | None = None) -> int:
    n = 0
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))):
        if s.id != except_id:
            s.revoked_at = utcnow()
            n += 1
    return n
