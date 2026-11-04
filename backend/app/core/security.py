"""Password hashing, opaque session tokens, OTP codes, field encryption, TOTP."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)
_DUMMY_HASH = _hasher.hash("timing-equalizer-" + secrets.token_hex(8))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


COMMON_PASSWORDS = {
    "password", "password123", "12345678", "123456789", "1234567890", "qwerty123", "11111111",
    "00000000", "abcd1234", "iloveyou", "admin123", "welcome1", "p@ssw0rd", "passw0rd",
}


def password_problems(password: str, *, email: str | None = None, phone: str | None = None) -> list[str]:
    problems = []
    if len(password) < settings.password_min_length:
        problems.append("too_short")
    if len(password) > 128:
        problems.append("too_long")
    classes = sum(
        [any(c.islower() for c in password), any(c.isupper() for c in password),
         any(c.isdigit() for c in password), any(not c.isalnum() for c in password)]
    )
    if classes < 3:
        problems.append("too_simple")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS:
        problems.append("too_common")
    if email and email.split("@")[0].lower() in lowered and len(email.split("@")[0]) >= 4:
        problems.append("contains_identity")
    if phone and phone[-6:] in password:
        problems.append("contains_identity")
    return problems


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    """HMAC-SHA256 of an opaque token using the server secret (stored in DB instead of the token)."""
    return hmac.new(settings.secret_key.encode(), token.encode(), hashlib.sha256).hexdigest()


def new_numeric_code(digits: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(digits))


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _fernet() -> Fernet:
    key = settings.field_encryption_key
    if not key:
        # Derive a stable development key from SECRET_KEY. Production requires an explicit key.
        key = base64.urlsafe_b64encode(hashlib.sha256(("fernet:" + settings.secret_key).encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_field(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str | None:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name="WESAL")


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()
