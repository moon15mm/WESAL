from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import settings
from app.core.errors import AppError
from app.core.i18n import normalize_locale, t


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record), "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in ("request_id", "path", "method", "status", "duration_ms", "user_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_json else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)


configure_logging()
log = logging.getLogger("wesal.http")

problems = settings.validate_production()
if problems:
    raise RuntimeError("Refusing to start with insecure production configuration: " + "; ".join(problems))

app = FastAPI(
    title="WESAL API",
    version="1.0.0",
    description="WESAL | وِصال – Connected B2B marketplace for retail sales & distribution",
    docs_url="/api/docs" if not settings.is_production else "/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["content-type", "x-csrf-token", "x-business-id", "x-locale", "authorization", "x-auth-mode",
                   "idempotency-key"],
)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd and settings.trusted_proxies > 0:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-min(settings.trusted_proxies, len(parts))]
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.client_ip = _client_ip(request)
    started = time.perf_counter()
    response = await call_next(request)
    duration = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    if request.url.path.startswith("/api/v1"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    if not request.url.path.startswith("/api/v1/health"):
        log.info("request", extra={"request_id": request.state.request_id, "path": request.url.path,
                                   "method": request.method, "status": response.status_code, "duration_ms": duration})
    return response


def _locale(request: Request) -> str:
    return normalize_locale(request.headers.get("x-locale") or request.headers.get("accept-language"))


def _error(request: Request, status: int, code: str, params: dict | None = None, fields: dict | None = None):
    locale = _locale(request)
    params = params or {}
    body = {"error": {"code": code, "message": t(f"errors.{code}", locale, **params), "params": params,
                      "fields": fields or {}, "request_id": getattr(request.state, "request_id", None)}}
    headers = {"Retry-After": str(params["retry_after"])} if status == 429 and "retry_after" in params else None
    return JSONResponse(body, status_code=status, headers=headers)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return _error(request, exc.status_code, exc.code, exc.params, exc.fields)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    fields = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        fields[".".join(loc) or "_"] = err.get("type", "invalid")
    return _error(request, 422, "validation_failed", fields=fields)


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    log.warning("integrity error: %s", str(exc.orig)[:300])
    return _error(request, 409, "conflict")


@app.exception_handler(StarletteHTTPException)
async def http_handler(request: Request, exc: StarletteHTTPException):
    code = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized", 403: "forbidden"}.get(exc.status_code, "error")
    return _error(request, exc.status_code, code)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
    return _error(request, 500, "internal_error")


def include_routers() -> None:
    from app.modules.registry import ROUTERS

    for r in ROUTERS:
        app.include_router(r, prefix="/api/v1")


include_routers()
