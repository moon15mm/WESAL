"""Application errors. Every error carries a stable machine code; messages are
localized from app/locales/<locale>.json under `errors.<code>`."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, code: str | None = None, *, status_code: int | None = None, params: dict[str, Any] | None = None,
                 fields: dict[str, str] | None = None):
        self.code = code or self.code
        if status_code:
            self.status_code = status_code
        self.params = params or {}
        self.fields = fields or {}
        super().__init__(self.code)


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class InvalidTransition(AppError):
    status_code = 409
    code = "invalid_transition"


class IntegrationUnavailable(AppError):
    status_code = 503
    code = "integration_unavailable"
