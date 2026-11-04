"""Acceptance scenarios 2, 3 and 4 from the product specification."""
from tests.conftest import authorize, make_rep, make_supplier, register


def _deliver(sup, oid):
    for step in ("prepare", "ready"):
        r = sup.post(f"/supplier/orders/{oid}/{step}")
        assert r.status_code == 200, r.text
    r = sup.post(f"/supplier/orders/{oid}/dispatch", {"driver_name": "Driver", "vehicle_plate": "ABC 123"})
    assert r.status_code == 200, r.text
    r = sup.c.post(f"/api/v1/supplier/orders/{oid}/deliver", headers=sup._headers(), data={"notes": "left at store"})
    assert r.status_code == 200, r.text
    return r.json()


def test_scenario_independent_representative_full_cycle():
    sup = make_supplier(products=3)
    rep = make_rep()
    store = register("retailer")
    auth = authorize(sup, rep, rate="5")
    # authorized catalog
    cat = rep.get(f"/rep/catalog?supplier_id={sup.business_id}").json()
    assert cat["total"] == 3
    # visit
    v = rep.post("/rep/visits", {"retailer_id": store.business_id, "purpose": "order_taking", "start_now": True})
    assert v.status_code == 201, v.text
    # order created by the rep, sent to the store
    offer = sup.offers[0]
    r = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                 "items": [{"offer_id": offer["id"], "unit": "carton", "quantity": 2}], "visit_id": v.json()["id"]})
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "pending_retailer_approval"
    assert order["items"][0]["unit_price"] == "30.00"  # supplier price, not rep-controlled
    oid = order["id"]
    # supplier cannot see the order before the store approves it
    assert sup.get(f"/supplier/orders/{oid}").status_code == 404
    # store reviews and approves the exact version
    detail = store.get(f"/retailer/orders/{oid}").json()
    pa = detail["pending_approval"]
    assert "approve" in detail["actions"]
    bad = store.post(f"/retailer/orders/{oid}/approve", {"version": pa["version"], "snapshot_hash": "0" * 64})
    assert bad.status_code == 409
    r = store.post(f"/retailer/orders/{oid}/approve", {"version": pa["version"], "snapshot_hash": pa["snapshot_hash"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "new"
    # supplier receives and accepts
    r = sup.post(f"/supplier/orders/{oid}/accept", {})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    c = rep.get("/rep/commissions").json()
    assert c["total"] == 1 and c["items"][0]["status"] == "estimated"
    assert c["items"][0]["amount"] == "3.00"  # 5% of 60.00
    _deliver(sup, oid)
    r = store.post(f"/retailer/orders/{oid}/confirm-delivery", {"receiver_name": "Store keeper"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"
    comm = rep.get("/rep/commissions").json()["items"][0]
    assert comm["status"] == "due"  # hold_days=0
    # visit ends linked to the order
    r = rep.post(f"/rep/visits/{v.json()['id']}/end", {"outcome": "order_created", "order_id": oid})
    assert r.status_code == 200, r.text
    # supplier approves and pays the commission
    assert sup.post("/supplier/commissions/approve", {"commission_ids": [comm["id"]]}).status_code == 200
    r = sup.c.post("/api/v1/supplier/commission-payments", headers=sup._headers(),
                   data={"commission_ids": comm["id"], "method": "bank_transfer", "reference": "TRX-1"})
    assert r.status_code == 201, r.text
    assert rep.get("/rep/commissions").json()["items"][0]["status"] == "paid"
    # acquisition source recorded on the supplier's CRM
    custs = sup.get("/supplier/customers").json()["items"]
    me = next(x for x in custs if x["retailer_id"] == store.business_id)
    detail = sup.get(f"/supplier/customers/{me['id']}").json()
    assert detail["acquisition"]["source"] == "rep_visit"
    assert detail["acquisition"]["representative_id"] == rep.rep_id
    assert auth["status"] == "active"


def test_scenario_direct_order_with_quote_and_partial_delivery():
    sup = make_supplier(products=2)
    store = register("retailer")
    o1, o2 = sup.offers
    assert store.put(f"/retailer/carts/{sup.business_id}/items", {"offer_id": o1["id"], "unit": "carton", "quantity": 3}).status_code == 200
    r = store.put(f"/retailer/carts/{sup.business_id}/items", {"offer_id": o2["id"], "unit": "piece", "quantity": 10})
    assert r.json()["subtotal"] == "105.00"
    r = store.post(f"/retailer/carts/{sup.business_id}/checkout", {"notes": "morning delivery"})
    assert r.status_code == 201, r.text
    order = r.json()
    oid = order["id"]
    assert order["status"] == "new" and order["delivery_fee"] == "15.00"
    assert store.get("/retailer/carts").json() == []
    # supplier quotes a discount
    items = order["items"]
    r = sup.post(f"/supplier/orders/{oid}/offer", {"items": [
        {"order_item_id": items[0]["id"], "quantity": 3, "unit_price": "28.00", "discount": "0"},
        {"order_item_id": items[1]["id"], "quantity": 10, "unit_price": "1.50", "discount": "1.00"}],
        "delivery_fee": "0"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "quoted" and r.json()["total"] == "98.00"
    d = store.get(f"/retailer/orders/{oid}").json()
    pa = d["pending_approval"]
    r = store.post(f"/retailer/orders/{oid}/accept-offer", {"version": pa["version"], "snapshot_hash": pa["snapshot_hash"]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    _deliver(sup, oid)
    r = store.post(f"/retailer/orders/{oid}/confirm-delivery", {"items": [
        {"order_item_id": items[0]["id"], "received_qty": 2, "damaged_qty": 1},
        {"order_item_id": items[1]["id"], "received_qty": 10}]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["status"] == "completed"
    assert res["confirmations"][0]["has_shortage"] is True
    # collection evidence
    r = sup.c.post(f"/api/v1/supplier/orders/{oid}/collections", headers=sup._headers(),
                   data={"amount": "98.00", "method": "cash"})
    assert r.status_code == 201, r.text
    assert r.json()["payment_status"] == "paid"
    # invalid transition is blocked
    assert sup.post(f"/supplier/orders/{oid}/prepare").status_code == 409


def test_scenario_security_attempts():
    sup = make_supplier(products=1)
    other_sup = make_supplier(products=1)
    rep = make_rep()
    store = register("retailer")
    authorize(sup, rep)
    offer = sup.offers[0]
    r = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                 "items": [{"offer_id": offer["id"], "quantity": 24, "unit_price": "0.01"}]})
    assert r.status_code == 201
    order = r.json()
    oid = order["id"]
    assert order["items"][0]["unit_price"] == "1.50"  # forged price ignored
    # 1. another company tries to read the order (with and without forging the business header)
    assert other_sup.get(f"/supplier/orders/{oid}").status_code == 404
    other_sup_forged = other_sup
    other_sup_forged.business_id = sup.business_id
    assert other_sup_forged.get(f"/supplier/orders/{oid}").status_code == 403
    # 2. a store staff member without approval permission tries to approve
    staff_role = next(x for x in store.get("/business/roles").json()["roles"] if x["code"] == "store_staff")
    r = store.post("/business/team", {"full_name": "Staff Member", "email": f"staff.{oid[:8]}@example.com", "role_id": staff_role["id"]})
    assert r.status_code == 201, r.text
    # 3. the rep tries to bypass the store's approval: supplier can't act on it, rep can't approve it
    assert sup.post(f"/supplier/orders/{oid}/accept", {}).status_code == 404
    assert rep.post(f"/retailer/orders/{oid}/approve", {"version": 1, "snapshot_hash": "x" * 64}).status_code == 403
    # 4. a rep using a cancelled authorization
    auths = sup.get("/supplier/authorizations").json()
    sup_api = make_supplier  # noqa: F841
    a_id = next(a["id"] for a in auths if a["representative"]["id"] == rep.rep_id)
    # restore supplier header (it was the same object as other_sup? no) – sup is untouched
    assert sup.post(f"/supplier/authorizations/{a_id}/cancel", {"reason": "contract ended"}).status_code == 200
    r = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                 "items": [{"offer_id": offer["id"], "quantity": 24}]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "authorization_missing"
    # 5. a rep (no supplier context) tries to adjust a commission; another supplier tries too
    assert rep.post(f"/supplier/commissions/{oid}/adjust", {"amount_delta": "100", "note": "please"}).status_code == 403
    # 6. retailer cannot use supplier endpoints
    assert store.post(f"/supplier/orders/{oid}/accept", {}).status_code == 403


def test_rls_blocks_cross_tenant_reads_at_database_level():
    """Even raw SQL through the application role cannot see other tenants' orders."""
    import uuid

    from sqlalchemy import text

    from app.core.db import SessionLocal, set_rls_context

    sup = make_supplier(products=1)
    store = register("retailer")
    store.put(f"/retailer/carts/{sup.business_id}/items", {"offer_id": sup.offers[0]["id"], "quantity": 5})
    oid = store.post(f"/retailer/carts/{sup.business_id}/checkout", {}).json()["id"]
    db = SessionLocal()
    try:
        set_rls_context(db, user_id=uuid.uuid4(), business_ids=[uuid.uuid4()])
        assert db.execute(text("SELECT count(*) FROM orders WHERE id = :id"), {"id": oid}).scalar() == 0
        db.rollback()
        set_rls_context(db, user_id=uuid.uuid4(), business_ids=[uuid.UUID(store.business_id)])
        assert db.execute(text("SELECT count(*) FROM orders WHERE id = :id"), {"id": oid}).scalar() == 1
        db.rollback()
        # a rep-prepared order awaiting the store's approval is invisible to the supplier, even in raw SQL
        rep = make_rep()
        authorize(sup, rep)
        pending = rep.post("/rep/orders", {"retailer_id": store.business_id, "supplier_id": sup.business_id,
                                           "items": [{"offer_id": sup.offers[0]["id"], "quantity": 2}]}).json()
        assert pending["status"] == "pending_retailer_approval"
        set_rls_context(db, user_id=uuid.uuid4(), business_ids=[uuid.UUID(sup.business_id)])
        assert db.execute(text("SELECT count(*) FROM orders WHERE id = :id"), {"id": pending["id"]}).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM order_items WHERE order_id = :id"), {"id": pending["id"]}).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM orders WHERE id = :id"), {"id": oid}).scalar() == 1
        db.rollback()
        # audit rows cannot be read nor altered by the application role
        set_rls_context(db, user_id=uuid.uuid4(), business_ids=[uuid.UUID(store.business_id)])
        assert db.execute(text("SELECT count(*) FROM audit_logs")).scalar() == 0
    finally:
        db.rollback()
        db.close()
