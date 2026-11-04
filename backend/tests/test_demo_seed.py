"""The demo seeder drives the real API end to end; it doubles as a broad integration test."""
from sqlalchemy import func, select

from app.core.db import system_session


def test_demo_seed_produces_consistent_states(capsys):
    from app.models.commissions import Commission
    from app.models.orders import Order
    from app.seed.demo import seed_demo

    seed_demo()
    assert "demo data ready" in capsys.readouterr().out
    with system_session() as db:
        statuses = dict(db.execute(select(Order.status, func.count()).group_by(Order.status)).all())
        comm = dict(db.execute(select(Commission.status, func.count()).group_by(Commission.status)).all())
    got = {k.value: v for k, v in statuses.items()}
    for s in ("completed", "pending_retailer_approval", "quoted", "preparing", "out_for_delivery", "rejected", "cancelled", "new"):
        assert got.get(s), (s, got)
    assert {c.value for c in comm} >= {"paid", "pending", "estimated"}
