"""security: grants, row-level security policies, append-only triggers

Revision ID: 0002
Revises: 0001
"""
import os
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = os.environ.get("DB_APP_ROLE", "wesal_app")

HELPERS = """
CREATE OR REPLACE FUNCTION wesal_bypass() RETURNS boolean LANGUAGE sql STABLE AS
$$ SELECT coalesce(current_setting('wesal.bypass', true), 'off') = 'on' $$;
CREATE OR REPLACE FUNCTION wesal_bids() RETURNS uuid[] LANGUAGE sql STABLE AS
$$ SELECT CASE WHEN coalesce(current_setting('wesal.business_ids', true), '') = '' THEN ARRAY[]::uuid[]
           ELSE string_to_array(current_setting('wesal.business_ids', true), ',')::uuid[] END $$;
CREATE OR REPLACE FUNCTION wesal_rep() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('wesal.rep_id', true), '')::uuid $$;
CREATE OR REPLACE FUNCTION wesal_uid() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('wesal.user_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION wesal_block_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME USING ERRCODE = 'insufficient_privilege';
END $$;
"""

# table -> USING expression
POLICIES: dict[str, str] = {
    "orders": "retailer_id = ANY(wesal_bids()) OR supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "order_items": "EXISTS (SELECT 1 FROM orders o WHERE o.id = order_items.order_id)",
    "order_status_history": "EXISTS (SELECT 1 FROM orders o WHERE o.id = order_status_history.order_id)",
    "order_approvals": "EXISTS (SELECT 1 FROM orders o WHERE o.id = order_approvals.order_id)",
    "order_offers": "EXISTS (SELECT 1 FROM orders o WHERE o.id = order_offers.order_id)",
    "order_offer_items": "EXISTS (SELECT 1 FROM order_offers f WHERE f.id = order_offer_items.offer_id)",
    "delivery_records": "EXISTS (SELECT 1 FROM orders o WHERE o.id = delivery_records.order_id)",
    "delivery_confirmations": "EXISTS (SELECT 1 FROM orders o WHERE o.id = delivery_confirmations.order_id)",
    "order_collections": "EXISTS (SELECT 1 FROM orders o WHERE o.id = order_collections.order_id)",
    "returns": "retailer_id = ANY(wesal_bids()) OR supplier_id = ANY(wesal_bids())"
               " OR EXISTS (SELECT 1 FROM orders o WHERE o.id = returns.order_id)",
    "return_items": "EXISTS (SELECT 1 FROM returns r WHERE r.id = return_items.return_id)",
    "commissions": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "commission_adjustments": "EXISTS (SELECT 1 FROM commissions c WHERE c.id = commission_adjustments.commission_id)",
    "commission_disputes": "EXISTS (SELECT 1 FROM commissions c WHERE c.id = commission_disputes.commission_id)",
    "commission_payments": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "customers": "owner_supplier_id = ANY(wesal_bids()) OR owner_representative_id = wesal_rep()",
    "customer_contacts": "EXISTS (SELECT 1 FROM customers c WHERE c.id = customer_contacts.customer_id)",
    "customer_notes": "EXISTS (SELECT 1 FROM customers c WHERE c.id = customer_notes.customer_id)",
    "customer_assignments": "EXISTS (SELECT 1 FROM customers c WHERE c.id = customer_assignments.customer_id)",
    "customer_acquisition_records": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "customer_source_changes": "EXISTS (SELECT 1 FROM customer_acquisition_records a WHERE a.id = customer_source_changes.acquisition_id)",
    "opportunities": "owner_supplier_id = ANY(wesal_bids()) OR owner_representative_id = wesal_rep()",
    "visits": "representative_id = wesal_rep() OR supplier_id = ANY(wesal_bids())",
    "authorizations": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "authorization_products": "EXISTS (SELECT 1 FROM authorizations a WHERE a.id = authorization_products.authorization_id)",
    "authorization_areas": "EXISTS (SELECT 1 FROM authorizations a WHERE a.id = authorization_areas.authorization_id)",
    "authorization_history": "EXISTS (SELECT 1 FROM authorizations a WHERE a.id = authorization_history.authorization_id)",
    "rep_tasks": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "rep_targets": "supplier_id = ANY(wesal_bids()) OR representative_id = wesal_rep()",
    "carts": "user_id = wesal_uid()",
    "cart_items": "EXISTS (SELECT 1 FROM carts c WHERE c.id = cart_items.cart_id)",
    "notifications": "user_id = wesal_uid()",
    "business_documents": "business_id = ANY(wesal_bids())",
    "complaints": "raised_by_user_id = wesal_uid() OR raised_by_business_id = ANY(wesal_bids())"
                  " OR against_business_id = ANY(wesal_bids()) OR against_representative_id = wesal_rep()",
    "complaint_messages": "EXISTS (SELECT 1 FROM complaints c WHERE c.id = complaint_messages.complaint_id)",
    "ai_interactions": "user_id = wesal_uid()",
    "data_requests": "user_id = wesal_uid()",
}

APPEND_ONLY = ["audit_logs", "order_status_history", "authorization_history"]


def upgrade() -> None:
    op.execute(HELPERS)
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            CREATE ROLE {APP_ROLE} LOGIN;
          END IF;
        END $$;
        GRANT USAGE ON SCHEMA public TO {APP_ROLE};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
        GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {APP_ROLE};
        REVOKE ALL ON alembic_version FROM {APP_ROLE};
        """
    )
    for table in APPEND_ONLY:
        op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON {table} FROM {APP_ROLE}")
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION wesal_block_mutation()"
        )

    for table, expr in POLICIES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (wesal_bypass() OR {expr})")

    # audit_logs: anyone may append, only privileged context may read
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY audit_insert ON audit_logs FOR INSERT WITH CHECK (true)")
    op.execute("CREATE POLICY audit_select ON audit_logs FOR SELECT USING (wesal_bypass())")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_insert ON audit_logs")
    op.execute("DROP POLICY IF EXISTS audit_select ON audit_logs")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    for table in POLICIES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS wesal_block_mutation()")
    for fn in ("wesal_bypass", "wesal_bids", "wesal_rep", "wesal_uid"):
        op.execute(f"DROP FUNCTION IF EXISTS {fn}()")
