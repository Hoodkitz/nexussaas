"""Migration: webhook_inbox, outbox_events, RLS policies."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "webhook_inbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("attempts", sa.Integer, default=0),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(255), unique=True, nullable=True),
        sa.Column("published", sa.Boolean, default=False, nullable=False),
        sa.Column("attempts", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    # RLS policies
    op.execute("ALTER TABLE tenants ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation_tenants ON tenants USING (id = current_setting('app.tenant_id', true)::uuid)")
    op.execute("CREATE POLICY tenant_isolation_jobs ON jobs USING (tenant_id = current_setting('app.tenant_id', true)::uuid)")
    op.execute("CREATE POLICY tenant_isolation_memberships ON tenant_memberships USING (tenant_id = current_setting('app.tenant_id', true)::uuid)")

def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation_memberships ON tenant_memberships")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_jobs ON jobs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_tenants ON tenants")
    op.execute("ALTER TABLE tenant_memberships DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE jobs DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenants DISABLE ROW LEVEL SECURITY")
    op.drop_table("outbox_events")
    op.drop_table("webhook_inbox")
