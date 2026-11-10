from tests.conftest import PASSWORD, needs_services

pytestmark = needs_services


def test_register_login_me(make_account, client):
    a = make_account("anna")
    r = client.post("/api/v1/auth/login", json={"email": a.email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "owner"
    me = a.get("/api/v1/auth/me").json()
    assert me["user"]["email"] == a.email and len(me["tenants"]) == 1


def test_wrong_password_and_unknown_user(make_account, client):
    a = make_account()
    assert client.post("/api/v1/auth/login", json={"email": a.email, "password": "Falsch12345"}).status_code == 401
    assert client.post("/api/v1/auth/login",
                       json={"email": "nobody@example.com", "password": PASSWORD}).status_code == 401


def test_duplicate_and_weak_password(make_account, client):
    a = make_account()
    assert client.post("/api/v1/auth/register", json={"email": a.email, "password": PASSWORD}).status_code == 409
    assert client.post("/api/v1/auth/register",
                       json={"email": "weak@example.com", "password": "kurz"}).status_code == 422


def test_password_is_hashed(make_account):
    from packages.domain.models import User
    from packages.storage.db import new_session

    a = make_account()
    db = new_session()
    u = db.query(User).filter(User.email == a.email).one()
    db.close()
    assert u.hashed_password.startswith("$argon2id$") and PASSWORD not in u.hashed_password


def test_logout_all_revokes(make_account):
    a = make_account()
    assert a.post("/api/v1/auth/logout-all").status_code == 204
    assert a.get("/api/v1/auth/me").status_code == 401


def test_create_second_tenant_and_switch(make_account):
    a = make_account()
    r = a.post("/api/v1/tenants", json={"name": "Zweite Firma"})
    assert r.status_code == 201
    new_tid = r.json()["tenant_id"]
    assert len(a.get("/api/v1/auth/me").json()["tenants"]) == 2
    r = a.post("/api/v1/auth/switch-tenant", json={"tenant_id": new_tid})
    assert r.status_code == 200 and r.json()["tenant_id"] == new_tid


def test_google_not_configured_or_url(client, monkeypatch):
    from packages.settings import settings

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "")
    assert client.get("/api/v1/auth/google").status_code == 503
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "sec")
    url = client.get("/api/v1/auth/google").json()["authorization_url"]
    assert "code_challenge_method=S256" in url and "state=" in url


def test_google_callback_rejects_unknown_state(client):
    assert client.get("/api/v1/auth/google/callback", params={"code": "x", "state": "nope"}).status_code == 400


def test_google_link_drops_unverified_password(make_account, client, monkeypatch):
    """Pre-hijacking: a password set by someone else on an unverified account is removed."""
    from apps.api.routers import auth as auth_router
    from packages.security import oidc

    a = make_account("victim")
    attacker = make_account("attacker")
    assert a.post("/api/v1/tenants/current/members", json={"email": attacker.email, "role": "admin"}).status_code == 201
    oidc_state = {"verifier": "v", "nonce": "n", "next": None}
    monkeypatch.setattr(oidc, "consume_state", lambda s: oidc_state)

    async def fake_exchange(code, verifier):
        return {"access_token": "x"}

    async def fake_info(tok):
        return {"sub": "google-sub-" + a.email, "email": a.email, "email_verified": True, "name": "V"}

    monkeypatch.setattr(oidc, "exchange_code", fake_exchange)
    monkeypatch.setattr(oidc, "fetch_userinfo", fake_info)
    assert auth_router.oidc is oidc
    r = client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "s"})
    assert r.status_code == 200
    assert a.get("/api/v1/auth/me").status_code == 401  # old sessions revoked
    assert client.post("/api/v1/auth/login", json={"email": a.email, "password": PASSWORD}).status_code == 401
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    members = client.get("/api/v1/tenants/current/members", headers=h).json()
    assert [m["email"] for m in members] == [a.email]  # attacker removed
