from datetime import timedelta

from app.core.utils import utcnow
from tests.conftest import make_supplier, register, uid


def test_supplier_catalog_and_marketplace_visibility():
    unverified = make_supplier(products=1, verified=False)
    sup = make_supplier(products=2)
    store = register("retailer")
    # unverified supplier is not visible in the market
    ids = [s["id"] for s in store.get("/market/suppliers?page_size=100").json()["items"]]
    assert sup.business_id in ids and unverified.business_id not in ids
    offers = store.get(f"/market/offers?supplier_id={sup.business_id}").json()
    assert offers["total"] == 2
    assert offers["items"][0]["price"]["piece"]["net"] == "1.50"
    r = store.get(f"/market/offers?supplier_id={unverified.business_id}")
    assert r.json()["total"] == 0


def test_same_barcode_reuses_product_identity_and_compare_offers():
    a = make_supplier(products=0)
    b = make_supplier(products=0)
    barcode = "628" + str(uid().__hash__() % 10**10).zfill(10)
    body = {"product": {"name_ar": "عصير برتقال", "name_en": "Orange juice", "category_id": 2, "barcode": barcode},
            "unit_price": "2.00", "pieces_per_carton": 12}
    pa = a.post("/supplier/products", body).json()
    body["unit_price"] = "1.80"
    pb = b.post("/supplier/products", body).json()
    assert pa["product"]["id"] == pb["product"]["id"]
    store = register("retailer")
    res = store.get(f"/market/products/{pa['product']['id']}").json()
    assert len(res["offers"]) == 2
    assert res["offers"][0]["price"]["piece"]["net"] == "1.80"  # cheapest first
    # search by Arabic with folded letters
    found = store.get("/market/products", params={"q": "عصير برتقال"}).json()
    assert any(p["id"] == pa["product"]["id"] for p in found["items"])


def test_customer_price_list_and_promotion():
    sup = make_supplier(products=1)
    store = register("retailer")
    other = register("retailer")
    offer = sup.offers[0]
    r = sup.post("/supplier/price-lists", {"name": "VIP", "type": "customer", "customer_business_ids": [store.business_id],
                                            "items": [{"offer_id": offer["id"], "unit_price": "1.20"}]})
    assert r.status_code == 201, r.text
    now = utcnow()
    r = sup.post("/supplier/promotions", {"name": "10% off", "kind": "percent", "value": "10", "offer_id": offer["id"],
                                          "starts_at": (now - timedelta(hours=1)).isoformat(),
                                          "ends_at": (now + timedelta(days=1)).isoformat()})
    assert r.status_code == 201, r.text
    mine = store.get(f"/market/offers?supplier_id={sup.business_id}").json()["items"][0]["price"]["piece"]
    theirs = other.get(f"/market/offers?supplier_id={sup.business_id}").json()["items"][0]["price"]["piece"]
    assert mine["list"] == "1.20" and mine["net"] == "1.08"
    assert theirs["list"] == "1.50" and theirs["net"] == "1.35"


def test_permissions_and_isolation_on_offers():
    sup = make_supplier(products=1)
    other = make_supplier(products=0)
    offer_id = sup.offers[0]["id"]
    assert other.patch(f"/supplier/products/{offer_id}", {"unit_price": "0.10"}).status_code == 404
    assert other.get(f"/supplier/products/{offer_id}").status_code == 404
    store = register("retailer")
    assert store.get("/supplier/products").status_code == 403  # retailer has no supplier context
    # forged business header → denied and audited
    store.business_id = sup.business_id
    assert store.get("/supplier/products").status_code == 403


def test_csv_import():
    sup = make_supplier(products=0)
    csv_data = "name_ar,name_en,category_slug,unit_price,pieces_per_carton,carton_price\nحليب,Milk,dairy,3.25,12,36\nسيء,Bad,unknown,1,1,\n"
    r = sup.post("/supplier/products/import", files={"file": ("p.csv", csv_data.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1 and len(r.json()["errors"]) == 1
