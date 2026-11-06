"""RLS tenant isolation tests."""
import os
import pytest
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://nexussaas:nexussaas@localhost:5432/nexussaas")

@pytest.fixture
def engine():
    return create_engine(DATABASE_URL)

def test_rls_enabled(engine):
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND rowsecurity=true"
        ))
        tables = [r[0] for r in result]
        assert "tenants" in tables
        assert "jobs" in tables
        assert "tenant_memberships" in tables

def test_set_tenant_context(engine):
    with engine.connect() as conn:
        conn.execute(text("SET app.tenant_id = '00000000-0000-0000-0000-000000000001'"))
        result = conn.execute(text("SELECT current_setting('app.tenant_id', true)"))
        assert result.scalar() == "00000000-0000-0000-0000-000000000001"
