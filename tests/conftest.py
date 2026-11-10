"""Shared fixtures. Integration tests need Postgres + Redis (docker compose up -d db redis)."""
from __future__ import annotations

import os
import uuid

import pytest

# Tests use their own database and Redis DB so they never touch the live dev services.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://nexus_app:nexus_app@localhost:5432/nexussaas_test")
os.environ.setdefault("MIGRATION_DATABASE_URL", "postgresql+psycopg2://nexussaas:nexussaas@localhost:5432/nexussaas_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("RATE_LIMIT_AUTH_PER_MINUTE", "10000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")
os.environ.setdefault("STORAGE_LOCAL_DIR", "/tmp/nexussaas-test-objects")

from fastapi.testclient import TestClient  # noqa: E402

PASSWORD = "Geheim12345"


def _services_up() -> bool:
    try:
        from sqlalchemy import text

        from packages.storage.db import engine
        from packages.storage.redis import get_redis

        with engine.connect() as c:
            c.execute(text("SELECT 1 FROM tenants LIMIT 1"))
        get_redis().ping()
        return True
    except Exception:
        return False


SERVICES = _services_up()
needs_services = pytest.mark.skipif(not SERVICES, reason="Postgres/Redis not available or not migrated")


@pytest.fixture(scope="session")
def client():
    from apps.api.main import app

    return TestClient(app)


class Account:
    def __init__(self, client: TestClient, email: str, data: dict):
        self.client = client
        self.email = email
        self.token = data["access_token"]
        self.tenant_id = data["tenant_id"]

    @property
    def h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, url, **kw):
        return self.client.get(url, headers=self.h, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self.h, **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self.h, **kw)


@pytest.fixture
def make_account(client):
    def _make(name: str = "user") -> Account:
        email = f"{name}-{uuid.uuid4().hex[:10]}@example.com"
        r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "name": name})
        assert r.status_code == 201, r.text
        return Account(client, email, r.json())
    return _make
