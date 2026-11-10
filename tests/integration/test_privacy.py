"""DSGVO Art. 15 export and Art. 17 erasure."""
from sqlalchemy import text

from tests.conftest import PASSWORD, needs_services
from tests.integration.test_jobs_flow import BLUEPRINT

pytestmark = needs_services


def test_export_contains_user_data(make_account):
    a = make_account("exp")
    a.post("/api/v1/jobs", json={"blueprint": BLUEPRINT})
    data = a.get("/api/v1/users/me/export").json()
    assert data["user"]["email"] == a.email
    assert len(data["memberships"]) == 1 and len(data["jobs"]) == 1
    assert any(x["action"] == "job.created" for x in data["audit"])


def test_erasure_deletes_user_and_sole_tenant(make_account, client):
    from packages.storage.db import new_session
    from packages.storage.object_storage import get_storage

    a = make_account("del")
    jid = a.post("/api/v1/jobs", json={"blueprint": BLUEPRINT}).json()["id"]
    get_storage().put(f"tenants/{a.tenant_id}/jobs/{jid}/x.json", b"{}")
    r = a.client.request("DELETE", "/api/v1/users/me", headers=a.h, json={"confirm_email": "wrong@example.com"})
    assert r.status_code == 400
    r = a.client.request("DELETE", "/api/v1/users/me", headers=a.h, json={"confirm_email": a.email})
    assert r.status_code == 200 and r.json()["tenants_deleted"] == 1
    assert client.post("/api/v1/auth/login", json={"email": a.email, "password": PASSWORD}).status_code == 401
    db = new_session(a.tenant_id)
    try:
        assert db.execute(text("SELECT count(*) FROM jobs")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM users WHERE email=:e"), {"e": a.email}).scalar() == 0
    finally:
        db.close()
    assert not get_storage().exists(f"tenants/{a.tenant_id}/jobs/{jid}/x.json")


def test_sole_owner_with_members_must_transfer_first(make_account):
    a, b = make_account("a"), make_account("b")
    a.post("/api/v1/tenants/current/members", json={"email": b.email, "role": "member"})
    r = a.client.request("DELETE", "/api/v1/users/me", headers=a.h, json={"confirm_email": a.email})
    assert r.status_code == 409


def test_member_erasure_keeps_shared_tenant(make_account, client):
    a, b = make_account("a"), make_account("b")
    a.post("/api/v1/tenants/current/members", json={"email": b.email, "role": "member"})
    r = b.client.request("DELETE", "/api/v1/users/me", headers=b.h, json={"confirm_email": b.email})
    assert r.status_code == 200 and r.json()["tenants_left"] == 1
    emails = {m["email"] for m in a.get("/api/v1/tenants/current/members").json()}
    assert emails == {a.email}
