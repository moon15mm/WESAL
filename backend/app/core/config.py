"""Application settings loaded from environment variables.

All secrets come from the environment (or a .env file in development).
Nothing secret is committed to the repository.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    app_name: str = "WESAL"
    secret_key: str = Field(default="dev-insecure-secret-change-me", min_length=16)
    # Fernet key (urlsafe base64, 32 bytes) used to encrypt sensitive columns (MFA secrets...)
    field_encryption_key: str = ""

    # Runtime role: subject to row-level security. Owner role: migrations only.
    database_url: str = "postgresql+psycopg://wesal_app:wesal_app@localhost:5432/wesal"
    database_owner_url: str = "postgresql+psycopg://wesal_owner:wesal_owner@localhost:5432/wesal"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    redis_url: str = "redis://localhost:6379/0"

    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    cors_origins: list[str] = ["http://localhost:3000"]
    trusted_proxies: int = 1  # number of reverse proxies in front (for client IP resolution)

    cookie_domain: str | None = None
    cookie_secure: bool = False
    session_ttl_hours: int = 24 * 14
    session_idle_minutes: int = 60 * 24 * 3
    sensitive_session_ttl_hours: int = 12  # admins & supplier managers
    password_min_length: int = 10
    login_max_failures: int = 5
    login_lock_minutes: int = 15
    otp_ttl_minutes: int = 10
    mfa_enforce_admin: bool = True  # platform admin endpoints require TOTP-verified sessions
    otp_max_attempts: int = 5

    storage_dir: str = "./var/storage"
    max_upload_mb: int = 8

    # Notifications / integrations
    email_backend: Literal["smtp", "console", "memory"] = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "WESAL <no-reply@wesal.example>"
    smtp_starttls: bool = True
    sms_provider: Literal["none", "console", "memory", "unifonic", "twilio"] = "console"
    sms_sender: str = "WESAL"
    unifonic_app_sid: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    whatsapp_provider: Literal["none", "memory", "meta_cloud"] = "none"
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    push_provider: Literal["none", "memory", "webpush"] = "none"
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:ops@wesal.example"

    # AI assistant
    ai_enabled: bool = True
    ai_provider: Literal["local", "anthropic", "none"] = "local"
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-5-5"
    ai_max_tokens: int = 1024

    # Commerce defaults
    default_currency: str = "SAR"
    default_timezone: str = "Asia/Riyadh"
    default_locale: str = "ar"
    vat_rate: float = 0.15
    auto_complete_days: int = 3  # auto-complete delivered orders if retailer does not respond
    return_window_days: int = 7
    authorization_expiry_warning_days: int = 14

    rate_limit_enabled: bool = True
    rate_limit_backend: Literal["redis", "memory"] = "redis"

    demo_mode: bool = False
    log_level: str = "INFO"
    log_json: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate_production(self) -> list[str]:
        """Return a list of configuration problems that must block a production start."""
        problems: list[str] = []
        if self.is_production:
            if self.secret_key.startswith("dev-") or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be a random value of at least 32 characters")
            if not self.field_encryption_key:
                problems.append("FIELD_ENCRYPTION_KEY is required")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true behind HTTPS")
            if self.demo_mode:
                problems.append("DEMO_MODE must be false in production")
            if self.email_backend != "smtp":
                problems.append("EMAIL_BACKEND should be smtp in production")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
