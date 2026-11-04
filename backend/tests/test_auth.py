import pyotp

from tests.conftest import PASSWORD, Api, last_code, make_admin, register, unique_phone, uid


def test_register_retailer_creates_business_branch_and_requires_csrf():
    api = register("retailer")
    me = api.me
    assert me["email_verified"] and me["phone_verified"]
    assert me["memberships"][0]["type"] == "retailer"
    assert me["memberships"][0]["role"] == "retailer_owner"
    assert me["memberships"][0]["verification_status"] == "unverified"  # not trusted just by registering
    # CSRF: cookie-authenticated unsafe request without header is rejected
    r = api.c.post("/api/v1/auth/logout", headers={"x-locale": "en"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


def test_duplicate_and_weak_password():
    api = register("supplier")
    r = Api(None).post("/auth/register", {"account_type": "supplier", "full_name": "X Y", "email": api.email,
                                          "password": PASSWORD, "accept_terms": True, "business_name_ar": "شركة"})
    assert r.status_code == 409
    r = Api(None).post("/auth/register", {"account_type": "representative", "full_name": "X Y", "phone": unique_phone(),
                                          "password": "password", "accept_terms": True})
    assert r.status_code == 422 and r.json()["error"]["code"] == "weak_password"
    r = Api(None).post("/auth/register", {"account_type": "representative", "full_name": "X Y", "phone": unique_phone(),
                                          "password": PASSWORD, "accept_terms": False})
    assert r.status_code == 422


def test_login_logout_lockout_and_sessions():
    api = register("representative")
    a = Api(None)
    for _ in range(5):
        assert a.post("/auth/login", {"identifier": api.email, "password": "wrong-Pass1!"}).status_code == 401
    r = a.post("/auth/login", {"identifier": api.email, "password": PASSWORD})
    assert r.status_code == 401 and r.json()["error"]["code"] == "account_locked"


def test_login_with_phone_and_session_revoke():
    api = register("representative")
    b = Api(None)
    assert b.post("/auth/login", {"identifier": api.phone, "password": PASSWORD}).status_code == 200
    sessions = b.get("/auth/sessions").json()
    assert len(sessions) >= 2
    other = [s for s in sessions if not s["current"]][0]
    assert b.delete(f"/auth/sessions/{other['id']}").status_code == 200
    assert api.get("/auth/me").status_code == 401  # revoked session no longer works


def test_password_reset_flow_revokes_sessions():
    api = register("retailer")
    anon = Api(None)
    assert anon.post("/auth/password/forgot", {"identifier": api.email}).status_code == 200
    assert anon.post("/auth/password/forgot", {"identifier": "nobody@example.com"}).status_code == 200  # no enumeration
    token = last_code(api.email)
    new = "N3w!Passw0rd-x"
    assert anon.post("/auth/password/reset", {"identifier": api.email, "code": "bad-token-123", "new_password": new}).status_code == 422
    r = anon.post("/auth/password/reset", {"identifier": api.email, "code": token, "new_password": new})
    assert r.status_code == 200, r.text
    assert api.get("/auth/me").status_code == 401
    assert anon.post("/auth/login", {"identifier": api.email, "password": new}).status_code == 200
    # token is single-use
    assert anon.post("/auth/password/reset", {"identifier": api.email, "code": token, "new_password": new + "2"}).status_code == 422


def test_mfa_flow_and_admin_requires_mfa():
    admin = make_admin()
    a = Api(None)
    r = a.post("/auth/login", {"identifier": admin.me["email"], "password": PASSWORD})
    assert r.json()["mfa_required"] is True
    assert a.get("/auth/sessions").status_code == 401  # pending MFA session is restricted
    assert a.post("/auth/mfa/verify", {"code": "000000"}).status_code == 401
    assert a.post("/auth/mfa/verify", {"code": pyotp.TOTP(admin.totp).now()}).status_code == 200
    assert a.get("/auth/sessions").status_code == 200


def test_bearer_mode_for_api_clients():
    api = register("representative")
    a = Api(None)
    r = a.post("/auth/login", {"identifier": api.email, "password": PASSWORD}, headers={"x-auth-mode": "bearer"})
    token = r.json()["session_token"]
    from fastapi.testclient import TestClient
    from app.main import app

    fresh = TestClient(app)
    r = fresh.get("/api/v1/auth/me", headers={"authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # bearer requests do not need CSRF
    assert fresh.post("/api/v1/auth/logout", headers={"authorization": f"Bearer {token}"}).status_code == 200


def test_profile_update_locale():
    api = register("representative")
    r = api.patch("/auth/me", {"locale": "ur", "number_system": "arab", "timezone": "Asia/Riyadh", "document_locale": "en"})
    assert r.status_code == 200
    assert r.json()["locale"] == "ur" and r.json()["document_locale"] == "en"
    assert api.patch("/auth/me", {"timezone": "Mars/Base"}).status_code == 422
