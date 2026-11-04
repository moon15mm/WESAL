"""Backend localization: error messages, notifications, emails, PDF/report labels.

Catalogs live in app/locales/<code>.json. Keys are dotted paths. Missing keys fall
back to English then Arabic, and `scripts/check_locales.py` fails CI on gaps."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
SUPPORTED_LOCALES = ("ar", "en", "ur", "hi")
RTL_LOCALES = {"ar", "ur"}
DEFAULT_LOCALE = "ar"
_PARAM = re.compile(r"\{(\w+)\}")


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = str(v)
    return out


@lru_cache
def catalog(locale: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    return _flatten(json.loads(path.read_text(encoding="utf-8")))


_overrides: dict[str, dict[str, str]] = {}


def set_overrides(locale: str, values: dict[str, str]) -> None:
    _overrides[locale] = values


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    for part in value.split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in SUPPORTED_LOCALES:
            return code
    return DEFAULT_LOCALE


def direction(locale: str) -> str:
    return "rtl" if locale in RTL_LOCALES else "ltr"


def t(key: str, locale: str = DEFAULT_LOCALE, **params: Any) -> str:
    locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    text = _overrides.get(locale, {}).get(key) or catalog(locale).get(key) or catalog("en").get(key) or catalog("ar").get(key)
    if text is None:
        return key
    return _PARAM.sub(lambda m: str(params.get(m.group(1), m.group(0))), text)


def localized(value: dict | None, locale: str) -> str:
    """Pick a translation from a {"ar": .., "en": ..} JSON column."""
    if not value:
        return ""
    return value.get(locale) or value.get("en") or value.get("ar") or next(iter(value.values()), "")


def missing_keys() -> dict[str, list[str]]:
    reference = set(catalog("ar")) | set(catalog("en"))
    return {loc: sorted(reference - set(catalog(loc))) for loc in SUPPORTED_LOCALES}
