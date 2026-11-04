"""Reference data required in every environment (production included):
permissions, system roles, Saudi regions & cities, base categories, languages,
subscription plans and default platform settings. Idempotent."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import ALL_PERMISSIONS, SYSTEM_ROLES
from app.models.business import City, Region
from app.models.catalog import Category
from app.models.identity import Permission, Role, RolePermission
from app.models.system import ContentPage, Language, PlatformSetting, SubscriptionPlan

REGIONS = [
    ("RIY", "منطقة الرياض", "Riyadh Region", "ریاض ریجن", "रियाद क्षेत्र"),
    ("MAK", "منطقة مكة المكرمة", "Makkah Region", "مکہ ریجن", "मक्का क्षेत्र"),
    ("MED", "منطقة المدينة المنورة", "Madinah Region", "مدینہ ریجن", "मदीना क्षेत्र"),
    ("EST", "المنطقة الشرقية", "Eastern Province", "مشرقی صوبہ", "पूर्वी प्रांत"),
    ("QAS", "منطقة القصيم", "Al-Qassim Region", "قصیم ریجن", "क़सीम क्षेत्र"),
    ("ASR", "منطقة عسير", "Asir Region", "عسیر ریجن", "असीर क्षेत्र"),
    ("TAB", "منطقة تبوك", "Tabuk Region", "تبوک ریجن", "तबूक क्षेत्र"),
    ("HAI", "منطقة حائل", "Hail Region", "حائل ریجن", "हाइल क्षेत्र"),
    ("NBR", "منطقة الحدود الشمالية", "Northern Borders Region", "شمالی سرحدی ریجن", "उत्तरी सीमा क्षेत्र"),
    ("JAZ", "منطقة جازان", "Jazan Region", "جازان ریجن", "जाज़ान क्षेत्र"),
    ("NAJ", "منطقة نجران", "Najran Region", "نجران ریجن", "नजरान क्षेत्र"),
    ("BAH", "منطقة الباحة", "Al-Bahah Region", "الباحہ ریجن", "अल-बाहा क्षेत्र"),
    ("JOF", "منطقة الجوف", "Al-Jouf Region", "الجوف ریجن", "अल-जौफ़ क्षेत्र"),
]

CITIES = [
    ("RIY", "riyadh", "الرياض", "Riyadh", "ریاض", "रियाद", 24.7136, 46.6753),
    ("RIY", "kharj", "الخرج", "Al Kharj", "الخرج", "अल-ख़र्ज", 24.1556, 47.3120),
    ("RIY", "diriyah", "الدرعية", "Diriyah", "درعیہ", "दिरिया", 24.7341, 46.5751),
    ("RIY", "majmaah", "المجمعة", "Al Majmaah", "المجمعہ", "अल-मजमा", 25.9039, 45.3456),
    ("RIY", "dawadmi", "الدوادمي", "Ad Dawadmi", "الدوادمی", "अद-दवादमी", 24.5077, 44.3924),
    ("MAK", "jeddah", "جدة", "Jeddah", "جدہ", "जेद्दा", 21.4858, 39.1925),
    ("MAK", "makkah", "مكة المكرمة", "Makkah", "مکہ مکرمہ", "मक्का", 21.3891, 39.8579),
    ("MAK", "taif", "الطائف", "Taif", "طائف", "ताइफ़", 21.2703, 40.4158),
    ("MAK", "rabigh", "رابغ", "Rabigh", "رابغ", "राबिग़", 22.7986, 39.0349),
    ("MED", "madinah", "المدينة المنورة", "Madinah", "مدینہ منورہ", "मदीना", 24.5247, 39.5692),
    ("MED", "yanbu", "ينبع", "Yanbu", "ینبع", "यनबू", 24.0895, 38.0618),
    ("MED", "alula", "العلا", "AlUla", "العلا", "अल-उला", 26.6084, 37.9232),
    ("EST", "dammam", "الدمام", "Dammam", "دمام", "दम्माम", 26.4207, 50.0888),
    ("EST", "khobar", "الخبر", "Al Khobar", "الخبر", "अल-ख़ोबर", 26.2172, 50.1971),
    ("EST", "dhahran", "الظهران", "Dhahran", "ظہران", "धहरान", 26.2361, 50.0393),
    ("EST", "ahsa", "الأحساء", "Al Ahsa", "الاحساء", "अल-अहसा", 25.3833, 49.5868),
    ("EST", "jubail", "الجبيل", "Jubail", "جبیل", "जुबैल", 27.0046, 49.6460),
    ("EST", "qatif", "القطيف", "Qatif", "قطیف", "क़तीफ़", 26.5196, 50.0115),
    ("EST", "hafr_albatin", "حفر الباطن", "Hafar Al-Batin", "حفر الباطن", "हफ़र अल-बातिन", 28.4328, 45.9708),
    ("QAS", "buraidah", "بريدة", "Buraidah", "بریدہ", "बुरैदा", 26.3592, 43.9818),
    ("QAS", "unaizah", "عنيزة", "Unaizah", "عنیزہ", "उनैज़ा", 26.0840, 43.9940),
    ("QAS", "rass", "الرس", "Ar Rass", "الرس", "अर-रस", 25.8694, 43.4973),
    ("ASR", "abha", "أبها", "Abha", "ابہا", "अभा", 18.2164, 42.5053),
    ("ASR", "khamis_mushait", "خميس مشيط", "Khamis Mushait", "خمیس مشیط", "ख़मीस मुशैत", 18.3000, 42.7333),
    ("ASR", "bisha", "بيشة", "Bisha", "بیشہ", "बीशा", 20.0005, 42.6052),
    ("TAB", "tabuk", "تبوك", "Tabuk", "تبوک", "तबूक", 28.3835, 36.5662),
    ("HAI", "hail", "حائل", "Hail", "حائل", "हाइल", 27.5114, 41.7208),
    ("NBR", "arar", "عرعر", "Arar", "عرعر", "अरार", 30.9753, 41.0381),
    ("JAZ", "jazan", "جازان", "Jazan", "جازان", "जाज़ान", 16.8892, 42.5511),
    ("JAZ", "sabya", "صبيا", "Sabya", "صبیا", "सबया", 17.1495, 42.6254),
    ("NAJ", "najran", "نجران", "Najran", "نجران", "नजरान", 17.5656, 44.2289),
    ("BAH", "bahah", "الباحة", "Al Bahah", "الباحہ", "अल-बाहा", 20.0129, 41.4677),
    ("JOF", "sakaka", "سكاكا", "Sakaka", "سکاکا", "सकाका", 29.9697, 40.2064),
    ("JOF", "qurayyat", "القريات", "Al Qurayyat", "القریات", "अल-क़ुरय्यात", 31.3317, 37.3428),
]

CATEGORIES = [
    ("water", "droplets", "المياه", "Water", "پانی", "पानी"),
    ("beverages", "cup-soda", "العصائر والمشروبات", "Juices & beverages", "جوس اور مشروبات", "जूस और पेय"),
    ("dairy", "milk", "الألبان ومشتقاتها", "Dairy products", "دودھ کی مصنوعات", "डेयरी उत्पाद"),
    ("canned", "package", "الأغذية المعلبة", "Canned food", "ڈبہ بند غذا", "डिब्बाबंद भोजन"),
    ("staples", "wheat", "المواد الغذائية الأساسية", "Food staples", "بنیادی غذائی اشیاء", "मूल खाद्य सामग्री"),
    ("snacks", "cookie", "الوجبات الخفيفة", "Snacks", "اسنیکس", "स्नैक्स"),
    ("sweets", "candy", "الحلويات والشوكولاتة", "Sweets & chocolate", "مٹھائیاں اور چاکلیٹ", "मिठाई और चॉकलेट"),
    ("cleaning", "spray-can", "المنظفات", "Cleaning products", "صفائی کی مصنوعات", "सफ़ाई उत्पाद"),
    ("paper", "scroll", "الورقيات", "Paper products", "کاغذی مصنوعات", "काग़ज़ उत्पाद"),
    ("store_supplies", "store", "مستلزمات المحلات", "Store supplies", "دکان کا سامان", "दुकान की सामग्री"),
    ("personal_care", "sparkles", "منتجات العناية الشخصية", "Personal care", "ذاتی نگہداشت", "व्यक्तिगत देखभाल"),
]

LANGUAGES = [
    ("ar", "Arabic", "العربية", "rtl", 1),
    ("en", "English", "English", "ltr", 2),
    ("ur", "Urdu", "اردو", "rtl", 3),
    ("hi", "Hindi", "हिन्दी", "ltr", 4),
]

PLANS = [
    ("supplier_starter", "supplier", {"ar": "الموردون – أساسي", "en": "Supplier – Starter", "ur": "سپلائر – بنیادی", "hi": "आपूर्तिकर्ता – स्टार्टर"},
     0, 0, {"products": 200, "users": 3, "representatives": 5}, ["catalog", "orders", "reports_basic"], 1),
    ("supplier_growth", "supplier", {"ar": "الموردون – نمو", "en": "Supplier – Growth", "ur": "سپلائر – گروتھ", "hi": "आपूर्तिकर्ता – ग्रोथ"},
     499, 4990, {"products": 2000, "users": 15, "representatives": 50}, ["catalog", "orders", "crm", "commissions", "reports_full", "ai"], 2),
    ("supplier_enterprise", "supplier", {"ar": "الموردون – مؤسسات", "en": "Supplier – Enterprise", "ur": "سپلائر – انٹرپرائز", "hi": "आपूर्तिकर्ता – एंटरप्राइज़"},
     1499, 14990, {"products": None, "users": None, "representatives": None}, ["everything", "priority_support"], 3),
    ("retailer_free", "retailer", {"ar": "المحلات – مجاني", "en": "Retailer – Free", "ur": "دکان – مفت", "hi": "दुकान – मुफ़्त"},
     0, 0, {"branches": 3, "users": 5}, ["orders", "approvals", "reports_basic"], 1),
    ("rep_free", "representative", {"ar": "المندوبون – مجاني", "en": "Representative – Free", "ur": "نمائندہ – مفت", "hi": "प्रतिनिधि – मुफ़्त"},
     0, 0, {"authorizations": 10}, ["marketplace", "visits", "orders", "commissions"], 1),
]

SETTINGS = {
    "vat_rate": (0.15, True),
    "currency": ("SAR", True),
    "timezone": ("Asia/Riyadh", True),
    "terms_version": ("1.0", True),
    "registration_open": (True, True),
    "ai_enabled": (True, True),
    "auto_complete_days": (3, False),
    "return_window_days": (7, False),
    "support_email": ("support@wesal.example", True),
    "support_phone": ("+966500000000", True),
    "maintenance_mode": (False, True),
}


def seed_reference(db: Session) -> None:
    for code, scope in ALL_PERMISSIONS.items():
        if db.get(Permission, code) is None:
            db.add(Permission(code=code, module=code.split(".")[1], scope=scope))
    db.flush()
    for spec in SYSTEM_ROLES:
        role = db.scalar(select(Role).where(Role.code == spec["code"], Role.business_id.is_(None)))
        if role is None:
            role = Role(code=spec["code"], scope=spec["scope"], name=spec["name"], is_system=True)
            db.add(role)
            db.flush()
        role.name = spec["name"]
        have = {rp.permission_code for rp in role.permissions}
        for p in spec["perms"]:
            if p not in have:
                role.permissions.append(RolePermission(role_id=role.id, permission_code=p))
        for rp in list(role.permissions):
            if rp.permission_code not in spec["perms"]:
                role.permissions.remove(rp)

    region_ids = {}
    for i, (code, ar, en, ur, hi) in enumerate(REGIONS, start=1):
        region = db.scalar(select(Region).where(Region.code == code))
        if region is None:
            region = Region(id=i, code=code, name={})
            db.add(region)
        region.name = {"ar": ar, "en": en, "ur": ur, "hi": hi}
        region_ids[code] = region.id
    db.flush()
    for i, (rcode, code, ar, en, ur, hi, lat, lng) in enumerate(CITIES, start=1):
        city = db.scalar(select(City).where(City.code == code))
        if city is None:
            city = City(id=i, code=code, region_id=region_ids[rcode], name={})
            db.add(city)
        city.name = {"ar": ar, "en": en, "ur": ur, "hi": hi}
        city.lat, city.lng = lat, lng
    for i, (slug, icon, ar, en, ur, hi) in enumerate(CATEGORIES, start=1):
        cat = db.scalar(select(Category).where(Category.slug == slug))
        if cat is None:
            cat = Category(id=i, slug=slug, name={}, sort_order=i)
            db.add(cat)
        cat.name = {"ar": ar, "en": en, "ur": ur, "hi": hi}
        cat.icon = icon
    for code, name, native, direction, order in LANGUAGES:
        if db.get(Language, code) is None:
            db.add(Language(code=code, name=name, native_name=native, direction=direction, sort_order=order))
    for code, audience, name, pm, py, limits, features, order in PLANS:
        if db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == code)) is None:
            db.add(SubscriptionPlan(code=code, audience=audience, name=name, price_monthly=pm, price_yearly=py,
                                    limits=limits, features=features, sort_order=order))
    for key, (value, public) in SETTINGS.items():
        if db.get(PlatformSetting, key) is None:
            db.add(PlatformSetting(key=key, value=value, is_public=public))
    db.flush()
    # keep integer sequences ahead of explicit ids
    from sqlalchemy import text

    for table in ("regions", "cities", "categories"):
        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT COALESCE(MAX(id), 1) FROM {table}))"))

    seed_legal_pages(db)


LEGAL_DIR = __import__("pathlib").Path(__file__).with_name("legal")


def _parse_legal(path) -> tuple[str, str, str]:
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---"):
        _, front, body = raw.split("---", 2)
        for line in front.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip().strip('"')
    return meta.get("title", path.stem), meta.get("version", "1.0"), body.strip() + "\n"


def seed_legal_pages(db: Session) -> int:
    """Load the bundled legal drafts (app/seed/legal/<locale>/<slug>.md) into content_pages.
    A page edited by an administrator (updated_by set) is never overwritten."""
    n = 0
    for loc_dir in sorted(p for p in LEGAL_DIR.iterdir() if p.is_dir()):
        for f in sorted(loc_dir.glob("*.md")):
            title, version, body = _parse_legal(f)
            row = db.scalar(select(ContentPage).where(ContentPage.slug == f.stem, ContentPage.locale == loc_dir.name))
            if row is None:
                db.add(ContentPage(slug=f.stem, locale=loc_dir.name, title=title, body=body, version=version))
                n += 1
            elif row.updated_by is None and (row.version != version or row.body != body):
                row.title, row.body, row.version = title, body, version
                n += 1
    db.flush()
    return n
