"""Integration tests for API flow."""
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_full_flow():
    # 1. Health check
    r = client.get("/healthz")
    assert r.status_code == 200

    # 2. Create tenant
    r = client.post("/api/v1/tenants", json={"name": "Test Corp", "slug": "test-corp"})
    assert r.status_code == 200
    tenant_id = r.json()["id"]

    # 3. Login
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()

    # 4. Create job
    r = client.post("/api/v1/jobs", json={"blueprint": {"name": "test-app", "version": "1.0"}})
    assert r.status_code == 200
    assert r.json()["status"] == "RECEIVED"

    # 5. Cancel job
    job_id = r.json()["id"]
    r = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
