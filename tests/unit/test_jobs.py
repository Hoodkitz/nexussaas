"""Job API tests."""
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)

def test_create_job():
    r = client.post("/api/v1/jobs", json={"blueprint": {"name": "test"}})
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["status"] == "RECEIVED"

def test_get_job_not_found():
    r = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

def test_stripe_webhook_no_sig():
    r = client.post("/api/v1/webhooks/stripe", content=b"{}")
    assert r.status_code == 400
