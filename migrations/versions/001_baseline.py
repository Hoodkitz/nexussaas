"""Baseline schema: tenants, users, memberships, jobs, billing, outbox, RLS.

Revision ID: 001
"""
from alembic import op
from sqlalchemy import text

from packages.domain.models import Base
from packages.settings import settings

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "nexus_app"
TENANT_TABLES = ["jobs", "job_events", "audit_log", "subscriptions"]


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind)

    # Application role: no superuser, no BYPASSRLS.
    exists = bind.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE}).scalar()
    pw = settings.APP_DB_PASSWORD.replace("'", "''")
    if not exists:
        op.execute(f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE")
    else:
        op.execute(f"ALTER ROLE {APP_ROLE} LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS")

    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}")

    # Context helpers. Empty/missing setting -> NULL -> every policy denies (default deny).
    op.execute("""
        CREATE OR REPLACE FUNCTION app_tenant_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION app_user_id() RETURNS uuid LANGUAGE sql STABLE AS
        $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$
    """)

    for t in TENANT_TABLES + ["tenants", "tenant_memberships"]:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")

    for t in TENANT_TABLES:
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {t}
            USING (tenant_id = app_tenant_id())
            WITH CHECK (tenant_id = app_tenant_id())
        """)

    # Memberships: visible within the current tenant, and a user's own memberships.
    op.execute("""
        CREATE POLICY membership_read ON tenant_memberships FOR SELECT
        USING (tenant_id = app_tenant_id() OR user_id = app_user_id())
    """)
    op.execute("""
        CREATE POLICY membership_write ON tenant_memberships FOR ALL
        USING (tenant_id = app_tenant_id()) WITH CHECK (tenant_id = app_tenant_id())
    """)
    # Tenants: the current tenant, plus tenants the user belongs to (read only).
    op.execute("""
        CREATE POLICY tenant_read ON tenants FOR SELECT
        USING (id = app_tenant_id() OR id IN (
            SELECT tenant_id FROM tenant_memberships WHERE user_id = app_user_id()))
    """)
    op.execute("""
        CREATE POLICY tenant_write ON tenants FOR ALL
        USING (id = app_tenant_id()) WITH CHECK (id = app_tenant_id())
    """)

    # Narrow system view for the job reaper: ids only, owner-defined.
    op.execute("""
        CREATE OR REPLACE FUNCTION system_stale_jobs(older_than interval)
        RETURNS TABLE(job_id uuid, tenant_id uuid, status text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
        $$ SELECT id, tenant_id, status::text FROM jobs
           WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED','REJECTED',
                                'BLUEPRINT_APPROVAL','HUMAN_RELEASE_APPROVAL')
             AND updated_at < now() - older_than $$
    """)
    op.execute("REVOKE ALL ON FUNCTION system_stale_jobs(interval) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION system_stale_jobs(interval) TO {APP_ROLE}")
    # Tenant lookup by Stripe customer for webhooks without metadata.
    op.execute("""
        CREATE OR REPLACE FUNCTION system_tenant_for_customer(customer text)
        RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
        $$ SELECT tenant_id FROM subscriptions WHERE stripe_customer_id = customer LIMIT 1 $$
    """)
    op.execute("REVOKE ALL ON FUNCTION system_tenant_for_customer(text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION system_tenant_for_customer(text) TO {APP_ROLE}")

    # LangGraph checkpointer tables (created by the owner, granted via default privileges).
    from langgraph.checkpoint.postgres import PostgresSaver

    url = settings.MIGRATION_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
    op.execute(f"REVOKE ALL ON alembic_version FROM {APP_ROLE}")


def downgrade():
    for fn in ["system_stale_jobs(interval)", "system_tenant_for_customer(text)", "app_tenant_id()", "app_user_id()"]:
        op.execute(f"DROP FUNCTION IF EXISTS {fn} CASCADE")
    for t in ["checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations"]:
        op.execute(f"DROP TABLE IF EXISTS {t}")
    Base.metadata.drop_all(op.get_bind())
