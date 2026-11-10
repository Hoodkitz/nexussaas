"""Cross-tenant tests (Phase 2 acceptance): access across tenants is always denied."""
import uuid

import pytest
from sqlalchemy import text

from tests.conftest import PASSWORD, needs_services

pytestmark = needs_services


def test_cannot_read_foreign_tenant(make_account):
    a, b = make_account("a"), make_account("b")
    assert a.get(f"/api/v1/tenants/{b.tenant_id}").status_code == 404
    assert a.get(f"/api/v1/tenants/{a.tenant_id}").status_code == 200


def test_forged_tenant_claim_rejected(make_account):
    from packages.security.tokens import create_access_token

    a, b = make_account("a"), make_account("b")
    me = a.get("/api/v1/auth/me").json()
    forged = create_access_token(me["user"]["id"], b.tenant_id, 0)
    r = a.client.get("/api/v1/tenants/current", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


def test_switch_tenant_requires_membership(make_account):
    a, b = make_account("a"), make_account("b")
    assert a.post("/api/v1/auth/switch-tenant", json={"tenant_id": b.tenant_id}).status_code == 403


def test_members_list_scoped(make_account):
    a, _b = make_account("a"), make_account("b")
    emails = {m["email"] for m in a.get("/api/v1/tenants/current/members").json()}
    assert emails == {a.email}


def test_rls_default_deny_without_context():
    from packages.storage.db import new_session

    db = new_session()
    try:
        assert db.execute(text("SELECT count(*) FROM tenants")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM jobs")).scalar() == 0
        assert db.execute(text("SELECT count(*) FROM audit_log")).scalar() == 0
    finally:
        db.close()


def test_rls_blocks_cross_tenant_insert(make_account):
    from sqlalchemy.exc import ProgrammingError

    from packages.storage.db import new_session

    a, b = make_account("a"), make_account("b")
    db = new_session(a.tenant_id)
    try:
        with pytest.raises(ProgrammingError):
            db.execute(text("INSERT INTO audit_log (tenant_id, action) VALUES (:t, 'x')"), {"t": b.tenant_id})
            db.flush()
    finally:
        db.rollback()
        db.close()


def test_app_role_is_not_privileged():
    from packages.storage.db import engine

    with engine.connect() as c:
        row = c.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
    assert row == (False, False)


def test_rls_enabled_and_forced_on_tenant_tables():
    from packages.storage.db import engine

    with engine.connect() as c:
        rows = dict(c.execute(text(
            "SELECT relname, relrowsecurity AND relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('tenants','tenant_memberships','jobs','job_events','audit_log','subscriptions')"
        )).all())
    assert len(rows) == 6 and all(rows.values())


def test_rbac_viewer_cannot_add_members(make_account, client):
    a, b = make_account("a"), make_account("b")
    assert a.post("/api/v1/tenants/current/members", json={"email": b.email, "role": "viewer"}).status_code == 201
    tok = client.post("/api/v1/auth/login",
                      json={"email": b.email, "password": PASSWORD, "tenant_id": a.tenant_id}).json()
    assert tok["role"] == "viewer"
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    c = make_account("c")
    assert client.post("/api/v1/tenants/current/members", headers=h,
                       json={"email": c.email}).status_code == 403
    assert client.get("/api/v1/tenants/current/members", headers=h).status_code == 200


def test_admin_cannot_demote_owner(make_account, client):
    a, b = make_account("a"), make_account("b")
    a.post("/api/v1/tenants/current/members", json={"email": b.email, "role": "admin"})
    tok = client.post("/api/v1/auth/login",
                      json={"email": b.email, "password": PASSWORD, "tenant_id": a.tenant_id}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    me = a.get("/api/v1/auth/me").json()["user"]["id"]
    r = client.patch(f"/api/v1/tenants/current/members/{me}", headers=h, json={"role": "member"})
    assert r.status_code == 403


def test_last_owner_cannot_leave(make_account):
    a = make_account("a")
    me = a.get("/api/v1/auth/me").json()["user"]["id"]
    assert a.delete(f"/api/v1/tenants/current/members/{me}").status_code == 409


def test_removed_member_loses_access(make_account, client):
    a, b = make_account("a"), make_account("b")
    a.post("/api/v1/tenants/current/members", json={"email": b.email, "role": "member"})
    tok = client.post("/api/v1/auth/login",
                      json={"email": b.email, "password": PASSWORD, "tenant_id": a.tenant_id}).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    bid = client.get("/api/v1/auth/me", headers=h).json()["user"]["id"]
    assert a.delete(f"/api/v1/tenants/current/members/{bid}").status_code == 204
    assert client.get("/api/v1/tenants/current", headers=h).status_code == 403


def test_bad_tokens(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer abc"}).status_code == 401
    import jwt

    t = jwt.encode({"sub": str(uuid.uuid4()), "iss": "nexussaas", "typ": "access", "exp": 9999999999},
                   "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401
