"""Every error code / notification event used in code must be translated in all 4 locales."""
import pathlib
import re

from app.core.i18n import SUPPORTED_LOCALES, catalog, t
from app.modules.notifications.service import EVENTS

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
PATTERN = re.compile(r'(?:Forbidden|NotFound|Unauthorized|Conflict|ValidationFailed|RateLimited|InvalidTransition|'
                     r'IntegrationUnavailable|AppError)\("([a-z_]+)"')
AUTH_REASONS = ["authorization_missing", "authorization_not_effective", "authorization_no_order_rights",
                "authorization_area_not_covered", "authorization_product_not_covered"]


def used_error_codes() -> set[str]:
    codes = set(AUTH_REASONS)
    for f in APP.rglob("*.py"):
        codes |= set(PATTERN.findall(f.read_text(encoding="utf-8")))
    return codes


def test_all_error_codes_translated():
    for loc in SUPPORTED_LOCALES:
        cat = catalog(loc)
        missing = sorted(c for c in used_error_codes() if f"errors.{c}" not in cat)
        assert not missing, f"{loc} missing: {missing}"


def test_notification_events_translated():
    for loc in SUPPORTED_LOCALES:
        cat = catalog(loc)
        for e in EVENTS:
            assert f"notifications.{e}.title" in cat and f"notifications.{e}.body" in cat, (loc, e)


def test_same_keys_everywhere_and_params():
    ref = set(catalog("ar"))
    for loc in SUPPORTED_LOCALES:
        assert set(catalog(loc)) == ref, loc
    assert t("errors.below_min_order_value", "en", min="100") == "Minimum order value is SAR 100."
    assert "100" in t("errors.below_min_order_value", "ur", min="100")


def test_localized_error_response(client):
    r = client.get("/api/v1/auth/me", headers={"x-locale": "ar"})
    assert r.status_code == 401 and r.json()["error"]["message"] == "يلزم تسجيل الدخول."
    r = client.get("/api/v1/auth/me", headers={"accept-language": "hi-IN,hi;q=0.9"})
    assert r.json()["error"]["message"] == "कृपया साइन इन करें।"
