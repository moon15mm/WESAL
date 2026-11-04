"""Test harness: real PostgreSQL (RLS enforced, app connects as the restricted role),
migrations applied from scratch once per session, unique data per test."""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("ENV", "test")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://wesal_app:wesal_app@localhost:5432/wesal_test")
os.environ["DATABASE_OWNER_URL"] = os.environ.get("TEST_DATABASE_OWNER_URL", "postgresql+psycopg://wesal_owner:wesal_owner@localhost:5432/wesal_test")
os.environ["EMAIL_BACKEND"] = "memory"
os.environ["SMS_PROVIDER"] = "memory"
os.environ["WHATSAPP_PROVIDER"] = "memory"
os.environ["PUSH_PROVIDER"] = "none"
os.environ["RATE_LIMIT_BACKEND"] = "memory"
os.environ["AI_PROVIDER"] = "local"
os.environ["LOG_JSON"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["STORAGE_DIR"] = os.environ.get("TEST_STORAGE_DIR", "/tmp/wesal-test-storage")

import pyotp  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.core.db import system_session  # noqa: E402

BASE = os.path.dirname(os.path.dirname(__file__))
PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(scope="session", autouse=True)
def database():
    owner = os.environ["DATABASE_OWNER_URL"]
    eng = create_engine(owner)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    eng.dispose()
    cfg = Config(os.path.join(BASE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE, "alembic"))
    cfg.attributes["url"] = owner
    command.upgrade(cfg, "head")
    from app.seed.reference import seed_reference

    with system_session() as db:
        seed_reference(db)
        db.commit()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    ratelimit.reset_memory()
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, base_url="http://testserver") as c:
        yield c


def uid() -> str:
    return uuid.uuid4().hex[:10]


def unique_phone() -> str:
    n = uuid.uuid4().int % 10**7
    return f"+96655{n:07d}"


class Api:
    """Small helper around TestClient keeping cookies + CSRF per actor."""

    def __init__(self, client: TestClient, business_id: str | None = None):
        from app.main import app

        self.c = TestClient(app, base_url="http://testserver")
        self.business_id = business_id
        self.user_id = None
        self.me = None

    def _headers(self, extra=None):
        h = {"x-locale": "en"}
        csrf = self.c.cookies.get("wesal_csrf")
        if csrf:
            h["x-csrf-token"] = csrf
        if self.business_id:
            h["x-business-id"] = self.business_id
        h.update(extra or {})
        return h

    def get(self, url, **kw):
        return self.c.get("/api/v1" + url, headers=self._headers(kw.pop("headers", None)), **kw)

    def post(self, url, json=None, **kw):
        return self.c.post("/api/v1" + url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def patch(self, url, json=None, **kw):
        return self.c.patch("/api/v1" + url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def put(self, url, json=None, **kw):
        return self.c.put("/api/v1" + url, json=json, headers=self._headers(kw.pop("headers", None)), **kw)

    def delete(self, url, **kw):
        return self.c.delete("/api/v1" + url, headers=self._headers(kw.pop("headers", None)), **kw)

    def refresh_me(self):
        r = self.get("/auth/me")
        assert r.status_code == 200, r.text
        self.me = r.json()
        self.user_id = self.me["id"]
        return self.me


def last_code(target: str, template_prefix: str = "direct.") -> str:
    from app.models.system import NotificationDelivery

    with system_session() as db:
        row = db.scalars(select(NotificationDelivery).where(NotificationDelivery.target == target,
                                                            NotificationDelivery.template.startswith(template_prefix))
                         .order_by(NotificationDelivery.created_at.desc())).first()
        assert row is not None, f"no message for {target}"
        return row.payload["params"]["code"]


def register(account_type: str, *, verify: bool = True, city_id: int = 1, **extra) -> Api:
    api = Api(None)
    tag = uid()
    payload = {
        "account_type": account_type,
        "full_name": f"Test {account_type} {tag}",
        "email": f"{account_type}.{tag}@example.com",
        "phone": unique_phone(),
        "password": PASSWORD,
        "locale": "en",
        "accept_terms": True,
        "city_id": city_id,
    }
    if account_type in ("retailer", "supplier"):
        payload["business_name_ar"] = f"منشأة {tag}"
        payload["business_name_en"] = f"Business {tag}"
    payload.update(extra)
    r = api.post("/auth/register", payload)
    assert r.status_code == 201, r.text
    api.email = payload["email"]
    api.phone = payload["phone"]
    if verify:
        for channel, target in (("email", payload["email"]), ("sms", payload["phone"])):
            code = last_code(target)
            rr = api.post("/auth/verify/confirm", {"channel": channel, "code": code})
            assert rr.status_code == 200, rr.text
    me = api.refresh_me()
    if me["memberships"]:
        api.business_id = me["memberships"][0]["business_id"]
    return api


def make_admin() -> Api:
    from app.core.security import hash_password
    from app.core.utils import utcnow
    from app.models.enums import UserStatus
    from app.models.identity import Role, User, UserRole

    tag = uid()
    email = f"admin.{tag}@example.com"
    with system_session() as db:
        u = User(email=email, full_name="Admin " + tag, password_hash=hash_password(PASSWORD), status=UserStatus.active,
                 email_verified_at=utcnow())
        db.add(u)
        db.flush()
        role = db.scalar(select(Role).where(Role.code == "platform_admin"))
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()
    api = Api(None)
    r = api.post("/auth/login", {"identifier": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    setup = api.post("/auth/mfa/setup").json()
    r = api.post("/auth/mfa/enable", {"code": pyotp.TOTP(setup["secret"]).now()})
    assert r.status_code == 200, r.text
    api.totp = setup["secret"]
    api.refresh_me()
    return api


@pytest.fixture
def admin() -> Api:
    return make_admin()


def verify_business(business_id: str) -> None:
    from app.core.utils import utcnow
    from app.models.business import Business
    from app.models.enums import VerificationStatus

    with system_session() as db:
        b = db.get(Business, uuid.UUID(business_id))
        b.verification_status = VerificationStatus.verified
        b.verified_at = utcnow()
        db.commit()


def verify_rep(rep_id: str) -> None:
    from app.core.utils import utcnow
    from app.models.enums import VerificationStatus
    from app.models.reps import Representative

    with system_session() as db:
        r = db.get(Representative, uuid.UUID(rep_id))
        r.verification_status = VerificationStatus.verified
        r.verified_at = utcnow()
        db.commit()


def make_supplier(products: int = 3, verified: bool = True, city_ids=(1,)) -> Api:
    sup = register("supplier")
    if verified:
        verify_business(sup.business_id)
    r = sup.put("/supplier/coverage", [{"city_id": c, "delivery_fee": "15.00", "lead_time_days": 1} for c in city_ids])
    assert r.status_code == 200, r.text
    sup.offers = []
    for i in range(products):
        tag = uid()
        r = sup.post("/supplier/products", {
            "product": {"name_ar": f"مياه {tag}", "name_en": f"Water {tag}", "category_id": 1, "package_size": "330 ml"},
            "unit_price": "1.50", "carton_price": "30.00", "pieces_per_carton": 24, "min_order_qty": 1,
        })
        assert r.status_code == 201, r.text
        sup.offers.append(r.json())
    return sup


def png_bytes() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (16, 43, 70)).save(buf, format="PNG")
    return buf.getvalue()


def make_rep(verified: bool = True, city_id: int = 1) -> Api:
    rep = register("representative", city_id=city_id)
    r = rep.post("/rep/documents", data={"doc_type": "national_id"}, files={"file": ("id.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    assert rep.post("/rep/verification/submit").status_code == 200
    if verified:
        verify_rep(rep.me["representative"]["id"])
    rep.refresh_me()
    rep.rep_id = rep.me["representative"]["id"]
    return rep


def authorize(sup: Api, rep: Api, *, rate: str = "5", hold_days: int = 0, city_ids=(1,), all_products=True) -> dict:
    g = sup.post("/supplier/commission-agreements", {"name": "Std", "hold_days": hold_days,
                                                     "rules": [{"basis": "percent", "rate": rate}]})
    assert g.status_code == 201, g.text
    r = rep.post("/rep/authorizations", {"supplier_id": sup.business_id, "message": "I cover Riyadh"})
    assert r.status_code == 201, r.text
    auth_id = r.json()["id"]
    from datetime import date

    r = sup.post(f"/supplier/authorizations/{auth_id}/issue", {
        "type": "full_sales", "agreement_id": g.json()["id"], "all_products": all_products, "all_areas": False,
        "areas": [{"city_id": c} for c in city_ids], "start_date": date.today().isoformat(),
        "products": [] if all_products else [{"category_id": 2}],
    })
    assert r.status_code == 200, r.text
    r = rep.post(f"/rep/authorizations/{auth_id}/accept", {"terms_hash": r.json()["terms_hash"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    return r.json()
