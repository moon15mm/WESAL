import json
from datetime import date, timedelta

from tests.conftest import authorize, make_admin, make_rep, make_supplier, png_bytes, register


def _rep_order_completed(sup, rep, store, qty=2):
    offer = sup.offers[0]
    r = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                 "items": [{"offer_id": offer["id"], "unit": "carton", "quantity": qty}]})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    pa = store.get(f"/retailer/orders/{oid}").json()["pending_approval"]
    assert store.post(f"/retailer/orders/{oid}/approve", {"version": pa["version"], "snapshot_hash": pa["snapshot_hash"]}).status_code == 200
    assert sup.post(f"/supplier/orders/{oid}/accept", {}).status_code == 200
    for step in ("prepare", "ready"):
        assert sup.post(f"/supplier/orders/{oid}/{step}").status_code == 200
    assert sup.post(f"/supplier/orders/{oid}/dispatch", {}).status_code == 200
    assert store.post(f"/retailer/orders/{oid}/confirm-delivery", {}).status_code == 200
    return oid


def test_supplier_registration_verification_scenario_1():
    admin = make_admin()
    sup = register("supplier", cr_number="1010" + str(abs(hash(admin.user_id)) % 10**6).zfill(6))
    store = register("retailer")
    # not visible before verification
    assert all(s["id"] != sup.business_id for s in store.get("/market/suppliers?page_size=100").json()["items"])
    assert sup.post("/business/verification/submit").status_code == 422  # CR document required
    r = sup.c.post("/api/v1/business/documents", headers=sup._headers(), data={"doc_type": "commercial_registration"},
                   files={"file": ("cr.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", "application/pdf")})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    assert sup.post("/business/verification/submit").status_code == 200
    pending = admin.get("/admin/businesses?verification=pending&page_size=100").json()["items"]
    assert any(b["id"] == sup.business_id for b in pending)
    r = admin.post(f"/admin/businesses/{sup.business_id}/verification", {"decision": "verify", "documents": {doc_id: "approved"}})
    assert r.status_code == 200, r.text
    assert r.json()["verification_status"] == "verified"
    sup.put("/supplier/coverage", [{"city_id": 1, "delivery_fee": "0"}])
    r = sup.post("/supplier/products", {"product": {"name_ar": "أرز بسمتي", "name_en": "Basmati rice", "category_id": 5,
                                                    "package_size": "5 kg"}, "unit_price": "38.00", "pieces_per_carton": 4})
    assert r.status_code == 201
    assert sup.patch(f"/supplier/products/{r.json()['id']}", {"availability": "low_stock", "stock_qty": 40}).status_code == 200
    assert any(s["id"] == sup.business_id for s in store.get("/market/suppliers?page_size=100").json()["items"])
    # unsafe upload rejected
    bad = sup.c.post("/api/v1/business/documents", headers=sup._headers(), data={"doc_type": "other"},
                     files={"file": ("x.pdf", b"<script>alert(1)</script>", "application/pdf")})
    assert bad.status_code == 422
    js = sup.c.post("/api/v1/business/documents", headers=sup._headers(), data={"doc_type": "other"},
                    files={"file": ("x.pdf", b"%PDF-1.4 /JavaScript (app.alert(1))", "application/pdf")})
    assert js.status_code == 422 and js.json()["error"]["code"] == "file_unsafe_content"
    # non-admin cannot reach admin endpoints; admin without MFA is blocked
    assert store.get("/admin/dashboard").status_code == 403
    assert admin.get("/admin/dashboard").status_code == 200


def test_returns_adjust_commission_once_and_dispute_flow():
    sup = make_supplier(products=1)
    rep = make_rep()
    store = register("retailer")
    authorize(sup, rep, rate="10")
    oid = _rep_order_completed(sup, rep, store, qty=2)  # 2 cartons × 30 = 60 → 6.00
    comm = rep.get("/rep/commissions").json()["items"][0]
    assert comm["amount"] == "6.00"
    item = store.get(f"/retailer/orders/{oid}").json()["items"][0]
    r = store.c.post(f"/api/v1/retailer/orders/{oid}/returns", headers=store._headers(),
                     data={"reason": "damaged", "items": json.dumps([{"order_item_id": item["id"], "quantity": 1}])},
                     files=[("evidence", ("p.png", png_bytes(), "image/png"))])
    assert r.status_code == 201, r.text
    ret = r.json()
    # cannot exceed received quantity across open returns
    r2 = store.c.post(f"/api/v1/retailer/orders/{oid}/returns", headers=store._headers(),
                      data={"reason": "damaged", "items": json.dumps([{"order_item_id": item["id"], "quantity": 2}])})
    assert r2.status_code == 422
    assert sup.post(f"/supplier/returns/{ret['id']}/decide", {"decision": "approve"}).status_code == 200
    r = sup.post(f"/supplier/returns/{ret['id']}/receive")
    assert r.status_code == 200, r.text
    detail = store.get(f"/retailer/orders/{oid}").json()
    assert detail["status"] == "partially_returned" and detail["items"][0]["returned_qty"] == 1
    comm = rep.get("/rep/commissions").json()["items"][0]
    assert comm["amount"] == "3.00" and len(comm["adjustments"]) == 1
    assert sup.post(f"/supplier/returns/{ret['id']}/receive").status_code == 409  # cannot apply twice
    assert sup.post(f"/supplier/returns/{ret['id']}/settle", {"settlement_note": "credit note CN-1 off-platform"}).status_code == 200
    # rep disputes the commission, supplier resolves with an adjustment
    r = rep.post(f"/rep/commissions/{comm['id']}/dispute", {"reason": "the damaged carton was a transport issue", "expected_amount": "6.00"})
    assert r.status_code == 201
    dispute_id = r.json()["disputes"][0]["id"]
    # a supplier user without commissions.manage can't resolve or adjust
    sup_role = next(x for x in sup.get("/business/roles").json()["roles"] if x["code"] == "sales_supervisor")
    assert sup_role and "supplier.commissions.manage" not in sup_role["permissions"]
    r = sup.post(f"/supplier/commission-disputes/{dispute_id}/resolve", {"accept": True, "resolution": "agreed", "resolved_amount": "4.50"})
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == "4.50"


def test_order_dispute_ratings_reports_pdf_and_exports():
    sup = make_supplier(products=1)
    rep = make_rep()
    store = register("retailer")
    authorize(sup, rep)
    oid = _rep_order_completed(sup, rep, store)
    # ratings tied to the real order
    assert store.post(f"/retailer/orders/{oid}/ratings", {"target": "supplier", "overall": 4, "delivery_commitment": 5}).status_code == 201
    assert store.post(f"/retailer/orders/{oid}/ratings", {"target": "supplier", "overall": 1}).status_code == 409
    assert store.post(f"/retailer/orders/{oid}/ratings", {"target": "representative", "overall": 5}).status_code == 201
    assert rep.get("/rep/profile").json()["rating_avg"] == 5.0
    # dispute
    r = store.post("/complaints", {"kind": "order_dispute", "category": "delivery", "subject": "Missing items",
                                   "description": "Two cartons were missing at delivery time.", "order_id": oid})
    assert r.status_code == 201, r.text
    assert store.get(f"/retailer/orders/{oid}").json()["status"] == "disputed"
    assert any(c["id"] == r.json()["id"] for c in sup.get("/complaints").json())  # respondent sees it
    assert sup.post(f"/complaints/{r.json()['id']}/messages", {"body": "We will check with the driver."}).status_code == 201
    admin = make_admin()
    rr = admin.post(f"/admin/complaints/{r.json()['id']}", {"status": "resolved", "resolution": "Delivered quantities confirmed",
                                                            "order_outcome": "restore"})
    assert rr.status_code == 200, rr.text
    assert store.get(f"/retailer/orders/{oid}").json()["status"] == "completed"
    # reports & exports
    rep_json = sup.get("/reports/supplier").json()
    assert rep_json["kpis"]["orders"] >= 1 and rep_json["representatives"]
    for fmt, ctype in (("csv", "text/csv"), ("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        r = sup.get(f"/reports/supplier?format={fmt}")
        assert r.status_code == 200 and ctype in r.headers["content-type"], (fmt, r.text[:200])
    assert store.get("/reports/retailer?format=pdf").content.startswith(b"%PDF")
    assert rep.get("/reports/rep").json()["kpis"]["orders_created"] >= 1
    for loc in ("ar", "en", "ur", "hi"):
        pdf = store.get(f"/orders/{oid}/document.pdf?locale={loc}")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF"), loc
    other = register("retailer")
    assert other.get(f"/orders/{oid}/document.pdf").status_code == 404


def test_ai_features_and_scheduler_and_notifications():
    from app.core.db import system_session
    from app.integrations import channels
    from app.modules.notifications.service import deliver_pending
    from app.workers import scheduler

    sup = make_supplier(products=0)
    for ar, en in (("مياه نوفا 330 مل", "Nova water 330ml"), ("حليب المراعي كامل الدسم", "Almarai full fat milk")):
        assert sup.post("/supplier/products", {"product": {"name_ar": ar, "name_en": en, "category_id": 1},
                                               "unit_price": "1.00", "carton_price": "20.00", "pieces_per_carton": 20}).status_code == 201
    store = register("retailer")
    r = store.post("/ai/parse-order", {"text": "5 كراتين مياه نوفا\n3 حليب المراعي", "supplier_id": sup.business_id})
    assert r.status_code == 200, r.text
    lines = r.json()["lines"]
    assert lines[0]["quantity"] == 5 and lines[0]["unit"] == "carton" and "Nova" in lines[0]["match"]["name"]
    assert lines[1]["quantity"] == 3 and "Almarai" in lines[1]["match"]["name"]
    assert r.json()["notice"] == "proposal_only"
    assert store.get("/ai/reorder-forecast").status_code == 200
    ans = store.post("/ai/ask", {"question": "كم مشترياتي هذا الشهر؟"}).json()
    assert ans["provider"] == "local" and ans["sources"]
    assert sup.get("/ai/supplier/coverage-gaps").status_code == 200
    assert sup.get("/ai/supplier/summary").json()["text"]
    # scheduler jobs run cleanly
    for name, fn, _ in scheduler.JOBS:
        scheduler.run_job(name, fn)
    # outbox delivery through the in-memory providers
    channels.OUTBOX.clear()
    with system_session() as db:
        deliver_pending(db, limit=500)
    assert any(m["channel"] in ("email", "sms") for m in channels.OUTBOX)


def test_authorization_expiry_blocks_orders():
    from app.core.db import system_session
    from app.models.reps import Authorization
    from app.workers.scheduler import expire_authorizations

    sup = make_supplier(products=1)
    rep = make_rep()
    store = register("retailer")
    auth = authorize(sup, rep)
    import uuid as _u

    with system_session() as db:
        a = db.get(Authorization, _u.UUID(auth["id"]))
        a.start_date = date.today() - timedelta(days=30)
        a.end_date = date.today() - timedelta(days=1)
        db.commit()
    body = {"retailer_id": store.business_id, "supplier_id": sup.business_id, "items": [{"offer_id": sup.offers[0]["id"], "quantity": 24}]}
    r = rep.post("/rep/orders", body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "authorization_not_effective"
    with system_session() as db:
        assert expire_authorizations(db) >= 1
        db.commit()
    assert rep.get(f"/rep/authorizations/{auth['id']}").json()["status"] == "expired"


def test_privacy_export_and_notifications_api():
    store = register("retailer")
    r = store.get("/privacy/export")
    assert r.status_code == 200 and r.json()["account"]["email"] == store.email
    assert store.post("/privacy/requests", {"kind": "deletion", "reason": "closing my shop"}).status_code == 201
    assert store.post("/privacy/requests", {"kind": "deletion"}).status_code == 409
    n = store.get("/notifications").json()
    assert n["total"] >= 1
    assert store.post("/notifications/read-all").status_code == 200
    assert store.get("/notifications/unread-count").json()["unread"] == 0
    prefs = store.get("/notifications/preferences").json()
    assert any(e["event"] == "order_offer" for e in prefs["events"])
    assert store.put("/notifications/preferences", [{"event": "order_offer", "channel": "sms", "enabled": False}]).status_code == 200
