"""Basic load test for the WESAL API (read-heavy marketplace traffic + order creation).

    backend/.venv/bin/python scripts/loadtest.py --base http://localhost:8000 --users 40 --seconds 60

Signs in the demo accounts once (DEMO environment only), then runs N concurrent virtual users that
browse the market, search, open dashboards and lists, and (10% of iterations) add to cart + check out.
Prints throughput, latency percentiles per endpoint and error counts. Rate limiting should be disabled on
the target (RATE_LIMIT_ENABLED=false) when measuring raw capacity, since all users share one IP.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time
from collections import defaultdict

import httpx

PASSWORD = "Wesal-Demo-2026"
STORES = ["demo.store.rayyan@example.com", "demo.store.hay@example.com", "demo.store.nada@example.com"]
SUPPLIERS = ["demo.supplier.nokhba@example.com", "demo.supplier.waha@example.com", "demo.supplier.sunbula@example.com"]
REPS = ["demo.rep.riyadh@example.com", "demo.rep.jeddah@example.com"]
QUERIES = ["مياه", "حليب", "أرز", "water", "juice", "عصير", "بسكويت"]


class Actor:
    def __init__(self, base: str, email: str):
        self.c = httpx.AsyncClient(base_url=base + "/api/v1", timeout=30, trust_env=False)
        self.email = email
        self.headers: dict[str, str] = {"x-locale": "ar"}

    async def login(self):
        r = await self.c.post("/auth/login", json={"identifier": self.email, "password": PASSWORD}, headers=self.headers)
        r.raise_for_status()
        self.headers["x-csrf-token"] = self.c.cookies.get("wesal_csrf") or ""
        me = (await self.c.get("/auth/me", headers=self.headers)).json()
        if me["memberships"]:
            self.headers["x-business-id"] = me["memberships"][0]["business_id"]
        self.me = me


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--users", type=int, default=40)
    ap.add_argument("--seconds", type=int, default=60)
    args = ap.parse_args()

    actors = {e: Actor(args.base, e) for e in STORES + SUPPLIERS + REPS}
    await asyncio.gather(*(a.login() for a in actors.values()))
    supplier_ids = [actors[e].headers["x-business-id"] for e in SUPPLIERS]
    lat: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, int] = defaultdict(int)
    deadline = time.perf_counter() + args.seconds

    async def call(a: Actor, name: str, method: str, url: str, **kw):
        t0 = time.perf_counter()
        try:
            r = await a.c.request(method, url, headers=a.headers, **kw)
            ok = r.status_code < 400 or (name == "checkout" and r.status_code in (409, 422))
        except httpx.HTTPError:
            ok, r = False, None
        lat[name].append((time.perf_counter() - t0) * 1000)
        if not ok:
            errors[f"{name} {r.status_code if r is not None else 'exc'}"] += 1
        return r

    async def store_user(a: Actor):
        rnd = random.Random()
        while time.perf_counter() < deadline:
            sid = rnd.choice(supplier_ids)
            r = await call(a, "market_offers", "GET", "/market/offers", params={"supplier_id": sid, "page_size": 24})
            await call(a, "search", "GET", "/market/products", params={"q": rnd.choice(QUERIES)})
            await call(a, "store_report", "GET", "/reports/retailer")
            await call(a, "store_orders", "GET", "/retailer/orders", params={"page_size": 20})
            if rnd.random() < 0.1 and r is not None and r.status_code == 200 and r.json()["items"]:
                offer = rnd.choice(r.json()["items"])
                await call(a, "cart_put", "PUT", f"/retailer/carts/{sid}/items", json={"offer_id": offer["id"], "quantity": 1})
                await call(a, "checkout", "POST", f"/retailer/carts/{sid}/checkout", json={})

    async def supplier_user(a: Actor):
        while time.perf_counter() < deadline:
            await call(a, "supplier_orders", "GET", "/supplier/orders", params={"page_size": 20})
            await call(a, "supplier_report", "GET", "/reports/supplier")
            await call(a, "supplier_products", "GET", "/supplier/products", params={"page_size": 50})

    async def rep_user(a: Actor):
        while time.perf_counter() < deadline:
            await call(a, "rep_catalog", "GET", "/rep/catalog")
            await call(a, "rep_performance", "GET", "/ai/rep/performance")
            await call(a, "rep_commissions", "GET", "/rep/commissions")

    tasks = []
    for i in range(args.users):
        kind = i % 10
        if kind < 6:
            tasks.append(store_user(actors[STORES[i % len(STORES)]]))
        elif kind < 8:
            tasks.append(supplier_user(actors[SUPPLIERS[i % len(SUPPLIERS)]]))
        else:
            tasks.append(rep_user(actors[REPS[i % len(REPS)]]))
    t0 = time.perf_counter()
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0
    total = sum(len(v) for v in lat.values())
    print(f"\n{args.users} virtual users · {elapsed:.0f}s · {total} requests · {total / elapsed:.1f} req/s · errors {sum(errors.values())}")
    print(f"{'endpoint':<20}{'n':>7}{'p50 ms':>9}{'p95 ms':>9}{'p99 ms':>9}{'max ms':>9}")
    allv = []
    for name, v in sorted(lat.items()):
        v.sort()
        allv += v
        q = statistics.quantiles(v, n=100) if len(v) > 1 else [v[0]] * 99
        print(f"{name:<20}{len(v):>7}{q[49]:>9.0f}{q[94]:>9.0f}{q[98]:>9.0f}{v[-1]:>9.0f}")
    allv.sort()
    q = statistics.quantiles(allv, n=100)
    print(f"{'ALL':<20}{len(allv):>7}{q[49]:>9.0f}{q[94]:>9.0f}{q[98]:>9.0f}{allv[-1]:>9.0f}")
    for k, n in sorted(errors.items()):
        print(f"  error {k}: {n}")
    for a in actors.values():
        await a.c.aclose()


if __name__ == "__main__":
    asyncio.run(main())
