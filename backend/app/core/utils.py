from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

import phonenumbers
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.orders import OrderSequence

_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي",
                         "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
                         "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
                         "ک": "ك", "ی": "ي", "ہ": "ه"})


def normalize_search(text: str | None) -> str:
    """Fold Arabic letter variants, strip diacritics/tatweel, unify digits, lowercase."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _AR_DIACRITICS.sub("", text).translate(_AR_MAP).lower()
    return re.sub(r"\s+", " ", text).strip()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_phone(raw: str | None, region: str = "SA") -> str | None:
    if not raw:
        return None
    raw = raw.translate(_AR_MAP)
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    return phone[:4] + "*" * max(len(phone) - 7, 0) + phone[-3:]


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    name, domain = email.split("@", 1)
    return (name[:2] + "***@" + domain) if len(name) > 2 else ("***@" + domain)


def slugify(value: str) -> str:
    value = normalize_search(value)
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    return re.sub(r"[\s_-]+", "-", value).strip("-")[:80] or "item"


def next_number(db: Session, prefix: str) -> str:
    """Gap-tolerant, concurrency-safe sequential numbers: e.g. WSL-2026-000123."""
    year = utcnow().year
    key = f"{prefix}-{year}"
    stmt = insert(OrderSequence).values(key=key, value=1).on_conflict_do_update(
        index_elements=[OrderSequence.key], set_={"value": OrderSequence.value + 1}
    ).returning(OrderSequence.value)
    value = db.execute(stmt).scalar_one()
    return f"{prefix}-{year}-{value:06d}"


__all__ = ["normalize_search", "utcnow", "money", "normalize_phone", "slugify", "next_number", "mask_phone",
           "mask_email", "select", "update"]
