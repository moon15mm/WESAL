"""Demo data for the DEMO environment only (DEMO_MODE=true, never production).

All businesses, people, brands and products below are fictional. Data is created by driving the real
API in-process (same validation, state machine, RLS, commission engine and audit trail as live use), so
every demo order/commission is in a state the application itself produced.

    python -m app.cli seed-demo          # add demo data to a database that has reference data
    python -m app.cli reset-demo         # drop + migrate + reference + demo  (demo environment only)

Every demo account uses the password in DEMO_PASSWORD; the account list is printed at the end.
"""
from __future__ import annotations

import io
import json
import random
import uuid
from datetime import date, timedelta

from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import system_session
from app.core.utils import utcnow

DEMO_PASSWORD = "Wesal-Demo-2026"
DOMAIN = "example.com"  # reserved documentation domain: never deliverable

SUPPLIERS = [
    {"key": "nokhba", "ar": "شركة النخبة للأغذية", "en": "Al Nokhba Foods Co.", "city": "riyadh", "cities": ["riyadh", "kharj", "diriyah"],
     "brand": ("ريف النخبة", "Nokhba Farms"), "color": (32, 185, 154),
     "products": [
         ("حليب طازج كامل الدسم 1 لتر", "Full-fat fresh milk 1L", "dairy", "1 L", "6.50", 12),
         ("لبن قليل الدسم 2 لتر", "Low-fat laban 2L", "dairy", "2 L", "9.75", 6),
         ("جبنة بيضاء 500 جم", "White cheese 500g", "dairy", "500 g", "14.25", 12),
         ("زبادي طبيعي 170 جم", "Plain yoghurt 170g", "dairy", "170 g", "1.50", 24),
         ("عصير برتقال 1 لتر", "Orange juice 1L", "beverages", "1 L", "7.25", 12),
         ("أرز بسمتي 5 كجم", "Basmati rice 5kg", "grocery", "5 kg", "42.00", 4),
         ("سكر أبيض 2 كجم", "White sugar 2kg", "grocery", "2 kg", "9.50", 10),
         ("زيت دوار الشمس 1.5 لتر", "Sunflower oil 1.5L", "grocery", "1.5 L", "16.75", 6),
     ]},
    {"key": "waha", "ar": "مصنع الواحة للمياه", "en": "Al Waha Water Factory", "city": "riyadh", "cities": ["riyadh", "jeddah"],
     "brand": ("نقاء الواحة", "Waha Pure"), "color": (59, 130, 196),
     "products": [
         ("مياه شرب 330 مل", "Drinking water 330ml", "beverages", "330 ml", "0.85", 40),
         ("مياه شرب 600 مل", "Drinking water 600ml", "beverages", "600 ml", "1.10", 30),
         ("مياه شرب 1.5 لتر", "Drinking water 1.5L", "beverages", "1.5 L", "1.75", 12),
         ("مياه غازية بنكهة الليمون 330 مل", "Sparkling lemon water 330ml", "beverages", "330 ml", "2.25", 24),
         ("مياه شرب 5 جالون", "Drinking water 5 gallon", "beverages", "18.9 L", "12.00", 1),
     ]},
    {"key": "sunbula", "ar": "مؤسسة السنبلة للتوزيع", "en": "Sunbula Distribution Est.", "city": "jeddah", "cities": ["jeddah", "riyadh"],
     "brand": ("سنبلة", "Sunbula"), "color": (229, 161, 59),
     "products": [
         ("خبز توست أبيض", "White toast bread", "bakery", "600 g", "5.50", 10),
         ("بسكويت شاي 12 حبة", "Tea biscuits 12 pcs", "snacks", "12 × 40 g", "8.00", 12),
         ("رقائق بطاطس بالملح 23 جم", "Salted potato chips 23g", "snacks", "23 g", "1.00", 48),
         ("مكرونة اسباجيتي 400 جم", "Spaghetti 400g", "grocery", "400 g", "3.25", 20),
         ("مناديل ورقية 200 منديل", "Facial tissues 200 sheets", "household", "200 sheets", "4.75", 30),
         ("سائل غسيل صحون 1 لتر", "Dishwashing liquid 1L", "household", "1 L", "8.90", 12),
     ]},
]

STORES = [
    {"key": "rayyan", "ar": "سوبرماركت الريان", "en": "Al Rayyan Supermarket", "city": "riyadh", "district": "حي النرجس",
     "branches": [("فرع النرجس", "riyadh", "حي النرجس"), ("فرع الياسمين", "riyadh", "حي الياسمين")]},
    {"key": "hay", "ar": "بقالة الحي الحديثة", "en": "Modern Neighbourhood Grocery", "city": "riyadh", "district": "حي الملقا", "branches": []},
    {"key": "nada", "ar": "أسواق الندى", "en": "Al Nada Markets", "city": "jeddah", "district": "حي الروضة",
     "branches": [("فرع الروضة", "jeddah", "حي الروضة")]},
]

REPS = [
    {"key": "rep_riyadh", "name": "سالم العتيبي", "city": "riyadh", "headline": "مندوب مبيعات مستقل — المواد الغذائية والمياه في الرياض",
     "langs": ["ar", "en"], "years": 7},
    {"key": "rep_jeddah", "name": "Imran Qureshi", "city": "jeddah", "headline": "Independent FMCG representative — Jeddah",
     "langs": ["ur", "en", "ar"], "years": 4},
]


class _Client:
    """In-process API client (cookies + CSRF), like a browser session."""

    def __init__(self):
        from fastapi.testclient import TestClient

        from app.main import app

        self.c = TestClient(app, base_url="https://demo.local")
        self.business_id: str | None = None
        self.me: dict | None = None

    def _h(self, extra=None):
        h = {"x-locale": "ar"}
        if csrf := self.c.cookies.get("wesal_csrf"):
            h["x-csrf-token"] = csrf
        if self.business_id:
            h["x-business-id"] = self.business_id
        h.update(extra or {})
        return h

    def call(self, method: str, url: str, json_body=None, expect=(200, 201), **kw):
        r = self.c.request(method, "/api/v1" + url, json=json_body, headers=self._h(kw.pop("headers", None)), **kw)
        if r.status_code not in expect:
            raise RuntimeError(f"{method} {url} → {r.status_code}: {r.text[:500]}")
        return r.json() if r.content else None

    def get(self, url, **kw):
        return self.call("GET", url, **kw)

    def post(self, url, body=None, **kw):
        return self.call("POST", url, body, **kw)

    def put(self, url, body=None, **kw):
        return self.call("PUT", url, body, **kw)

    def form(self, url, data=None, files=None):
        return self.call("POST", url, data=data, files=files)

    def login(self, email):
        self.post("/auth/login", {"identifier": email, "password": DEMO_PASSWORD})
        self.me = self.get("/auth/me")
        if self.me["memberships"]:
            self.business_id = self.me["memberships"][0]["business_id"]
        return self


_phone_seq = iter(range(5_000_100, 5_009_999))


def _phone() -> str:
    return f"+9665{next(_phone_seq):08d}"[:13]


def _activate(email: str, *, business_verified: bool = True) -> None:
    from app.models.business import Business, BusinessMember
    from app.models.enums import UserStatus, VerificationStatus
    from app.models.identity import User

    with system_session() as db:
        u = db.scalar(select(User).where(User.email == email))
        now = utcnow()
        u.email_verified_at = u.email_verified_at or now
        u.phone_verified_at = u.phone_verified_at or now
        u.status = UserStatus.active
        if business_verified:
            for m in db.scalars(select(BusinessMember).where(BusinessMember.user_id == u.id)):
                b = db.get(Business, m.business_id)
                b.verification_status, b.verified_at = VerificationStatus.verified, now
        db.commit()


def _register(kind: str, email: str, name: str, city_id: int, verified: bool = True, **extra) -> _Client:
    c = _Client()
    c.post("/auth/register", {"account_type": kind, "full_name": name, "email": email, "phone": _phone(), "password": DEMO_PASSWORD,
                              "locale": extra.pop("locale", "ar"), "accept_terms": True, "city_id": city_id, **extra})
    _activate(email, business_verified=verified)
    return c.login(email)


def _image(label: str, color: tuple[int, int, int], seed: int) -> bytes:
    """A clean, generated packshot-style placeholder (no third-party imagery)."""
    from PIL import Image, ImageDraw, ImageFont

    rnd = random.Random(seed)
    w = h = 480
    img = Image.new("RGB", (w, h), (245, 248, 250))
    d = ImageDraw.Draw(img)
    light = tuple(min(255, int(c + (255 - c) * 0.82)) for c in color)
    d.ellipse((60, 380, 420, 430), fill=(226, 232, 238))
    shape = rnd.choice(["box", "bottle", "bag"])
    if shape == "bottle":
        d.rounded_rectangle((185, 70, 295, 110), 12, fill=color)
        d.rounded_rectangle((150, 105, 330, 400), 48, fill=light, outline=color, width=6)
        d.rounded_rectangle((150, 210, 330, 310), 0, fill=color)
    elif shape == "bag":
        d.polygon([(130, 110), (350, 110), (380, 400), (100, 400)], fill=light, outline=color)
        d.rectangle((100, 230, 380, 320), fill=color)
    else:
        d.rounded_rectangle((110, 100, 370, 400), 22, fill=light, outline=color, width=6)
        d.rectangle((110, 220, 370, 310), fill=color)
    try:
        import pathlib

        font = ImageFont.truetype(str(pathlib.Path(__file__).parents[1] / "assets/fonts/inter-latin-700-normal.woff"), 34)
    except OSError:
        font = ImageFont.load_default()
    text = label[:14]
    tw = d.textlength(text, font=font)
    d.text(((w - tw) / 2, 245), text, fill="white", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _deliver(sup: _Client, oid: str, *, dispatch_only=False):
    for step in ("prepare", "ready"):
        sup.post(f"/supplier/orders/{oid}/{step}")
    sup.post(f"/supplier/orders/{oid}/dispatch", {"driver_name": "عبدالله", "vehicle_plate": "أ ب ج 1234"})
    if not dispatch_only:
        sup.form(f"/supplier/orders/{oid}/deliver", data={"notes": "تم التسليم لمسؤول المستودع"})


def _approve_pending(store: _Client, oid: str, accept_offer=False):
    pa = store.get(f"/retailer/orders/{oid}")["pending_approval"]
    path = "accept-offer" if accept_offer else "approve"
    return store.post(f"/retailer/orders/{oid}/{path}", {"version": pa["version"], "snapshot_hash": pa["snapshot_hash"]})


def seed_demo() -> None:
    from app.core import ratelimit
    from app.models.business import Business
    from app.models.catalog import Category
    from app.models.identity import Role, User, UserRole

    if settings.is_production:
        raise SystemExit("refusing to seed demo data in production")
    previous_rl = settings.rate_limit_enabled
    settings.rate_limit_enabled = False  # this process only (restored at the end)
    import logging

    for name in ("wesal.http", "httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    ratelimit.reset_memory()
    rnd = random.Random(2026)

    with system_session() as db:
        if db.scalar(select(User.id).where(User.email == f"demo.admin@{DOMAIN}")):
            raise SystemExit("demo data already present — use `reset-demo` to start over")
        from app.models.business import City as C

        city = {c.code: c.id for c in db.scalars(select(C))}
        cat = {c.slug: c.id for c in db.scalars(select(Category))}
        # platform admin (must enrol in MFA at first sign-in when MFA is enforced)
        from app.core.security import hash_password
        from app.models.enums import UserStatus

        admin = User(email=f"demo.admin@{DOMAIN}", full_name="مدير المنصة (تجريبي)", password_hash=hash_password(DEMO_PASSWORD),
                     status=UserStatus.active, email_verified_at=utcnow(), terms_version="1.0", terms_accepted_at=utcnow(),
                     password_changed_at=utcnow())
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role_id=db.scalar(select(Role.id).where(Role.code == "platform_admin"))))
        db.commit()

    accounts: list[tuple[str, str]] = [("platform admin", f"demo.admin@{DOMAIN}")]

    # ---- suppliers, brands, catalogue, coverage, pricing
    sups: dict[str, _Client] = {}
    for i, s in enumerate(SUPPLIERS):
        email = f"demo.supplier.{s['key']}@{DOMAIN}"
        sup = _register("supplier", email, f"مدير {s['ar']}", city[s["city"]], business_name_ar=s["ar"], business_name_en=s["en"],
                        cr_number=f"10{i + 1}0{rnd.randint(100000, 999999)}", vat_number=f"3{rnd.randint(10**12, 10**13 - 1)}3")
        sup.put("/supplier/coverage", [{"city_id": city[c], "delivery_fee": "0" if j == 0 else "25.00", "lead_time_days": 1 + j} for j, c in enumerate(s["cities"])])
        brand = sup.post("/supplier/brands", {"name_ar": s["brand"][0], "name_en": s["brand"][1], "manufacturer": s["en"], "country": "SA"})
        sup.offers = []
        for k, (ar, en, cslug, size, price, ppc) in enumerate(s["products"]):
            unit = float(price)
            carton = f"{unit * ppc * 0.95:.2f}" if ppc > 1 else None
            off = sup.post("/supplier/products", {
                "product": {"name_ar": ar, "name_en": en, "category_id": cat.get(cslug) or cat[next(iter(cat))], "brand_id": brand["id"],
                            "package_size": size, "barcode": f"6281{i}{k:02d}{rnd.randint(1000000, 9999999)}",
                            "description_ar": f"{ar} من {s['brand'][0]}. منتج تجريبي لأغراض العرض.",
                            "description_en": f"{en} by {s['brand'][1]}. Demo product for showcase purposes."},
                "sku": f"{s['key'][:3].upper()}-{k + 1:03d}", "unit_price": price, "carton_price": carton, "pieces_per_carton": ppc,
                "sell_by_piece": ppc <= 24, "sell_by_carton": ppc > 1, "min_order_qty": 1,
                "availability": "low_stock" if k == 2 else "in_stock", "stock_qty": 300 if k == 2 else 5000, "low_stock_threshold": 400})
            sup.form(f"/supplier/products/{off['id']}/image", files={"file": ("p.png", _image(s["brand"][1], s["color"], i * 100 + k), "image/png")})
            sup.offers.append(off)
        sups[s["key"]] = sup
        accounts.append((f"supplier · {s['en']}", email))

    # ---- stores and branches
    stores: dict[str, _Client] = {}
    for s in STORES:
        email = f"demo.store.{s['key']}@{DOMAIN}"
        st = _register("retailer", email, f"مالك {s['ar']}", city[s["city"]], business_name_ar=s["ar"], business_name_en=s["en"],
                       district=s["district"], address_line=f"{s['district']}، شارع تجريبي", store_type="supermarket")
        for bname, bcity, bdist in s["branches"]:
            st.post("/retailer/branches", {"name": bname, "city_id": city[bcity], "district": bdist, "address_line": f"{bdist}، شارع تجريبي"})
        stores[s["key"]] = st
        accounts.append((f"store · {s['en']}", email))

    # a new supplier that submitted its documents and waits for platform verification
    email = f"demo.supplier.pending@{DOMAIN}"
    pend = _register("supplier", email, "مدير مؤسسة البيدر", city["riyadh"], verified=False, business_name_ar="مؤسسة البيدر التجارية",
                     business_name_en="Al Baidar Trading Est.", cr_number=f"1010{rnd.randint(100000, 999999)}")
    pend.form("/business/documents", data={"doc_type": "commercial_registration"},
              files={"file": ("cr.png", _image("CR", (16, 43, 70), 11), "image/png")})
    pend.post("/business/verification/submit")
    accounts.append(("supplier awaiting verification", email))

    # customer price list + time-boxed promotion
    nok, waha, sun = sups["nokhba"], sups["waha"], sups["sunbula"]
    nok.post("/supplier/price-lists", {"name": "عملاء كبار الرياض", "type": "customer", "customer_business_ids": [stores["rayyan"].business_id],
                                       "items": [{"offer_id": nok.offers[0]["id"], "unit_price": "6.10"}, {"offer_id": nok.offers[5]["id"], "unit_price": "40.00"}]})
    now = utcnow()
    waha.post("/supplier/promotions", {"name": "Summer hydration", "name_ar": "عرض الصيف", "kind": "percent", "value": "8",
                                       "offer_id": waha.offers[0]["id"], "starts_at": (now - timedelta(days=2)).isoformat(),
                                       "ends_at": (now + timedelta(days=28)).isoformat()})

    # ---- representatives
    reps: dict[str, _Client] = {}
    for r in REPS:
        email = f"demo.{r['key'].replace('_', '.')}@{DOMAIN}"
        rc = _register("representative", email, r["name"], city[r["city"]], locale="ar" if r["langs"][0] == "ar" else "en")
        rc.form("/rep/documents", data={"doc_type": "national_id"}, files={"file": ("id.png", _image("ID", (16, 43, 70), 7), "image/png")})
        rc.c.patch("/api/v1/rep/profile", headers=rc._h(), json={
            "headline": r["headline"], "bio": r["headline"] + ". خبرة في التعامل مع البقالات والسوبرماركت.", "experience_years": r["years"],
            "languages": r["langs"], "availability": "available", "public_profile": True,
            "areas": [{"city_id": city[r["city"]]}], "category_ids": [cat[c] for c in ("beverages", "dairy", "grocery") if c in cat]})
        rc.post("/rep/verification/submit")
        from app.models.enums import VerificationStatus
        from app.models.reps import Representative

        rc.me = rc.get("/auth/me")
        with system_session() as db:
            rp = db.get(Representative, uuid.UUID(rc.me["representative"]["id"]))
            rp.verification_status, rp.verified_at = VerificationStatus.verified, utcnow()
            db.commit()
        rc.rep_id = rc.me["representative"]["id"]
        reps[r["key"]] = rc
        accounts.append((f"independent rep · {r['name']}", email))
    rr, rj = reps["rep_riyadh"], reps["rep_jeddah"]

    def authorize(sup: _Client, rep: _Client, *, rate: str, cities: list[str], hold_days=7, accept=True, all_products=True):
        g = sup.post("/supplier/commission-agreements", {"name": f"عمولة {rate}%", "hold_days": hold_days,
                                                          "rules": [{"basis": "percent", "rate": rate}]})
        a = rep.post("/rep/authorizations", {"supplier_id": sup.business_id, "message": "أغطي هذه المنطقة ولدي قاعدة عملاء من البقالات."})
        if not accept:
            return a
        issued = sup.post(f"/supplier/authorizations/{a['id']}/issue", {
            "type": "full_sales", "agreement_id": g["id"], "all_products": all_products, "all_areas": False,
            "areas": [{"city_id": city[c]} for c in cities], "start_date": (date.today() - timedelta(days=40)).isoformat(),
            "end_date": (date.today() + timedelta(days=320)).isoformat(),
            "terms": "يلتزم المندوب بأسعار المورد المعتمدة في المنصة، ولا يحق له تحصيل المبالغ نقداً."})
        return rep.post(f"/rep/authorizations/{a['id']}/accept", {"terms_hash": issued["terms_hash"]})

    authorize(nok, rr, rate="4", cities=["riyadh", "diriyah"])
    authorize(waha, rr, rate="6", cities=["riyadh"], hold_days=0)
    authorize(sun, rj, rate="5", cities=["jeddah"])
    authorize(waha, rj, rate="5", cities=["jeddah"], accept=False)  # request awaiting the supplier

    # company (employee) representative of Al Nokhba
    nok.post("/supplier/reps/company", {"full_name": "ماجد الحربي", "email": f"demo.rep.company@{DOMAIN}", "phone": _phone(), "employee_code": "NK-014"})
    from app.core.security import hash_password
    from app.models.enums import UserStatus

    with system_session() as db:
        u = db.scalar(select(User).where(User.email == f"demo.rep.company@{DOMAIN}"))
        u.password_hash, u.status, u.email_verified_at, u.phone_verified_at = hash_password(DEMO_PASSWORD), UserStatus.active, utcnow(), utcnow()
        u.terms_version, u.terms_accepted_at = "1.0", utcnow()
        db.commit()
    accounts.append(("company rep · Al Nokhba", f"demo.rep.company@{DOMAIN}"))

    rayyan, hay, nada = stores["rayyan"], stores["hay"], stores["nada"]

    def rep_order(rep, sup, store, lines, *, visit=True):
        v = rep.post("/rep/visits", {"retailer_id": store.business_id, "purpose": "order_taking", "start_now": True}) if visit else None
        o = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                     "items": [{"offer_id": sup.offers[i]["id"], "unit": u, "quantity": q} for i, u, q in lines],
                                     **({"visit_id": v["id"]} if v else {})})
        if v:
            rep.post(f"/rep/visits/{v['id']}/end", {"outcome": "order_created", "order_id": o["id"], "notes": "تم أخذ الطلب وإرساله للمتجر للموافقة"})
        return o["id"]

    def direct_order(store, sup, lines, notes=None):
        for i, u, q in lines:
            store.put(f"/retailer/carts/{sup.business_id}/items", {"offer_id": sup.offers[i]["id"], "unit": u, "quantity": q})
        return store.post(f"/retailer/carts/{sup.business_id}/checkout", {"notes": notes} if notes else {})["id"]

    # 1) rep order → approved → delivered → completed → commission paid  (Waha, hold 0)
    o1 = rep_order(rr, waha, rayyan, [(0, "carton", 10), (2, "carton", 6)])
    _approve_pending(rayyan, o1)
    waha.post(f"/supplier/orders/{o1}/accept", {})
    _deliver(waha, o1)
    rayyan.post(f"/retailer/orders/{o1}/confirm-delivery", {"receiver_name": "أمين المستودع"})
    waha.form(f"/supplier/orders/{o1}/collections", data={"amount": waha.get(f"/supplier/orders/{o1}")["total"], "method": "bank_transfer",
                                                         "reference": "TRF-88231"})
    c1 = [c for c in rr.get("/rep/commissions")["items"] if c["order"] and c["order"]["id"] == o1][0]
    waha.post("/supplier/commissions/approve", {"commission_ids": [c1["id"]]})
    waha.form("/supplier/commission-payments", data={"commission_ids": c1["id"], "method": "bank_transfer", "reference": "COM-2026-001"})
    rayyan.post(f"/retailer/orders/{o1}/ratings", {"target": "supplier", "overall": 5, "delivery_commitment": 5,
                                                    "comment": "التزام ممتاز بالموعد"})
    rayyan.post(f"/retailer/orders/{o1}/ratings", {"target": "representative", "overall": 5, "comment": "مندوب متعاون وواضح"})

    # 2) rep order completed, commission pending hold period (Nokhba, hold 7)
    o2 = rep_order(rr, nok, hay, [(0, "carton", 4), (3, "carton", 2), (5, "piece", 3)])
    _approve_pending(hay, o2)
    nok.post(f"/supplier/orders/{o2}/accept", {})
    _deliver(nok, o2)
    hay.post(f"/retailer/orders/{o2}/confirm-delivery", {})

    # 3) rep order waiting for the store's approval (store must approve)
    rep_order(rr, nok, rayyan, [(1, "carton", 3), (4, "carton", 2)])
    # 4) rep order in Jeddah, approved and being prepared
    o4 = rep_order(rj, sun, nada, [(0, "carton", 5), (2, "carton", 3), (4, "carton", 2)])
    _approve_pending(nada, o4)
    sun.post(f"/supplier/orders/{o4}/accept", {})
    sun.post(f"/supplier/orders/{o4}/prepare")

    # 5) direct order with supplier counter-offer awaiting store decision
    o5 = direct_order(rayyan, nok, [(5, "carton", 2), (6, "carton", 3)], notes="التوصيل صباحاً قبل 10")
    items = rayyan.get(f"/retailer/orders/{o5}")["items"]
    nok.post(f"/supplier/orders/{o5}/offer", {"items": [
        {"order_item_id": items[0]["id"], "quantity": 2, "unit_price": items[0]["unit_price"], "discount": "5.00"},
        {"order_item_id": items[1]["id"], "quantity": 3, "unit_price": items[1]["unit_price"], "discount": "0"}],
        "delivery_fee": "0", "notes": "خصم خاص على الأرز لهذا الطلب"})
    # 6) direct order out for delivery
    o6 = direct_order(hay, waha, [(1, "carton", 8), (4, "piece", 6)])
    waha.post(f"/supplier/orders/{o6}/accept", {})
    _deliver(waha, o6, dispatch_only=True)
    # 7) direct order completed then partially returned
    o7 = direct_order(nada, sun, [(1, "carton", 4), (3, "carton", 5)])
    sun.post(f"/supplier/orders/{o7}/accept", {})
    _deliver(sun, o7)
    it7 = nada.get(f"/retailer/orders/{o7}")["items"]
    nada.post(f"/retailer/orders/{o7}/confirm-delivery", {"items": [
        {"order_item_id": it7[0]["id"], "received_qty": 4}, {"order_item_id": it7[1]["id"], "received_qty": 5}]})
    ret = nada.form(f"/retailer/orders/{o7}/returns", data={"reason": "damaged", "notes": "كرتون واحد ممزق",
                                                            "items": json.dumps([{"order_item_id": it7[0]["id"], "quantity": 1}])},
                    files=[("evidence", ("d.png", _image("DAMAGED", (216, 75, 75), 3), "image/png"))])
    sun.post(f"/supplier/returns/{ret['id']}/decide", {"decision": "approve", "notes": "سيتم الاستبدال مع الطلب القادم"})
    # 8) direct order rejected by supplier; 9) direct order cancelled by store; 10) new order waiting for supplier
    o8 = direct_order(nada, waha, [(4, "piece", 3)])
    waha.post(f"/supplier/orders/{o8}/reject", {"reason": "الكمية المطلوبة أقل من الحد الأدنى للتوصيل إلى جدة"})
    o9 = direct_order(hay, nok, [(2, "carton", 1)])
    hay.post(f"/retailer/orders/{o9}/cancel", {"reason": "تم الطلب بالخطأ"})
    direct_order(rayyan, sun, [(0, "carton", 6), (5, "carton", 2)])

    # complaint about the out-for-delivery order
    hay.post("/complaints", {"kind": "complaint", "category": "delivery", "subject": "تأخر التوصيل",
                             "description": "الطلب خرج للتوصيل منذ الصباح ولم يصل بعد.", "order_id": o6, "against_business_id": waha.business_id})

    # scheduled visits + supplier tasks + CRM note
    for d, st in ((1, rayyan), (2, hay), (3, rayyan)):
        rr.post("/rep/visits", {"retailer_id": st.business_id, "supplier_id": nok.business_id, "purpose": "follow_up",
                                "scheduled_at": (utcnow() + timedelta(days=d, hours=2)).isoformat(), "notes": "متابعة الطلب الشهري"})
    rj.post("/rep/visits", {"retailer_id": nada.business_id, "supplier_id": sun.business_id, "purpose": "introduction",
                            "scheduled_at": (utcnow() + timedelta(days=1)).isoformat()})
    nok.post("/supplier/tasks", {"representative_id": rr.rep_id, "title": "عرض منتج الجبنة الجديد على سوبرماركت الريان",
                                 "due_at": (utcnow() + timedelta(days=3)).isoformat(), "priority": "high"})
    nok.post("/supplier/tasks", {"representative_id": rr.rep_id, "title": "تحصيل ملاحظات المتاجر عن عبوات اللبن 2 لتر",
                                 "due_at": (utcnow() + timedelta(days=7)).isoformat()})

    # demo messages are never delivered to real channels
    from app.models.enums import OutboxStatus
    from app.models.system import NotificationDelivery

    with system_session() as db:
        db.execute(update(NotificationDelivery).where(NotificationDelivery.status == OutboxStatus.pending)
                   .values(status=OutboxStatus.skipped, last_error="demo data"))
        n_biz = db.scalar(select(__import__("sqlalchemy").func.count(Business.id)))
        db.commit()

    settings.rate_limit_enabled = previous_rl
    print(f"demo data ready: {n_biz} businesses, password for every demo account: {DEMO_PASSWORD}")
    for role, email in accounts:
        print(f"  {role:<42} {email}")
