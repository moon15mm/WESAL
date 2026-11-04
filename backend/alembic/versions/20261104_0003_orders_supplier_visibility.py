"""security: suppliers cannot read orders that are still a draft or awaiting the store's approval

The API already hid these; this makes the database enforce it too (defence in depth). Child tables
(order_items, approvals, offers, deliveries, collections …) inherit through their EXISTS policies.

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW = ("wesal_bypass() OR retailer_id = ANY(wesal_bids()) OR representative_id = wesal_rep()"
       " OR (supplier_id = ANY(wesal_bids()) AND status NOT IN ('draft', 'pending_retailer_approval'))")
OLD = "wesal_bypass() OR retailer_id = ANY(wesal_bids()) OR supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()"


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON orders")
    op.execute(f"CREATE POLICY tenant_isolation ON orders USING ({NEW})")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON orders")
    op.execute(f"CREATE POLICY tenant_isolation ON orders USING ({OLD})")
