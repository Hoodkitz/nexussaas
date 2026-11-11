"""E-mail verification: registration sends a link; the link verifies; Google may link afterwards."""
from __future__ import annotations

import re


from packages.mail import get_mailer
from tests.conftest import needs_services

pytestmark = needs_services


def _last_link(email: str) -> str:
    mails = [m for m in get_mailer().sent if m.to == email]
    assert mails, "no verification mail recorded"
    m = re.search(r"token=([A-Za-z0-9._-]+)", mails[-1].text)
    assert m
    return m.group(1)


def test_register_sends_mail_and_link_verifies(make_account, client):
    a = make_account("verify")
    assert client.get("/api/v1/users/me/export").status_code == 401
    token = _last_link(a.email)
    r = client.get("/api/v1/auth/verify-email", params={"token": token})
    assert r.status_code == 200 and "bestätigt" in r.text  # the mail link shows a page
    assert a.get("/api/v1/users/me/export").json()["user"]["email_verified"] is True
    # idempotent
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200


def test_bad_or_foreign_token_rejected(make_account, client):
    a, b = make_account("x"), make_account("y")
    assert client.post("/api/v1/auth/verify-email", json={"token": "nonsense.token.value"}).status_code == 400
    # a token for b cannot verify a (sub/email bound) – and an access token is not a verify token
    assert client.post("/api/v1/auth/verify-email", json={"token": a.token}).status_code == 400
    assert b.get("/api/v1/users/me/export").json()["user"]["email_verified"] is False


def test_resend(make_account, client):
    a = make_account("resend")
    before = len([m for m in get_mailer().sent if m.to == a.email])
    assert a.post("/api/v1/auth/resend-verification").status_code == 202
    assert len([m for m in get_mailer().sent if m.to == a.email]) == before + 1
    client.get("/api/v1/auth/verify-email", params={"token": _last_link(a.email)})
    assert a.post("/api/v1/auth/resend-verification").json()["status"] == "already_verified"


def test_google_links_after_verification(make_account, client, monkeypatch):
    from tests.integration.test_auth import _fake_google

    a = make_account("linkme")
    client.get("/api/v1/auth/verify-email", params={"token": _last_link(a.email)})
    _fake_google(monkeypatch, "sub-" + a.email, a.email)
    r = client.get("/api/v1/auth/google/callback", params={"code": "c", "state": "s"})
    assert r.status_code == 200, r.text
    assert a.get("/api/v1/users/me/export").json()["user"]["google_linked"] is True


def test_require_verified_email_blocks_until_verified(make_account, client, monkeypatch):
    from packages.settings import settings

    a = make_account("gate")
    monkeypatch.setattr(settings, "REQUIRE_VERIFIED_EMAIL", True)
    assert a.get("/api/v1/auth/me").status_code == 200           # exempt
    assert a.post("/api/v1/auth/resend-verification").status_code == 202
    assert a.get("/api/v1/tenants/me").status_code == 403        # gated
    client.get("/api/v1/auth/verify-email", params={"token": _last_link(a.email)})
    assert a.get("/api/v1/tenants/me").status_code != 403


def test_password_reset_single_use(make_account, client):
    import re
    a = make_account("reset")
    assert client.post("/api/v1/auth/password-reset", json={"email": a.email}).status_code == 202
    assert client.post("/api/v1/auth/password-reset", json={"email": "nobody@example.com"}).status_code == 202
    mail = [m for m in get_mailer().sent if m.to == a.email][-1]
    token = re.search(r"token=([\w.-]+)", mail.text).group(1)
    assert "Neues Passwort" in client.get("/api/v1/auth/password-reset/confirm", params={"token": token}).text
    r = client.post("/api/v1/auth/password-reset/confirm", content=f"token={token}&password=NeuesPass123&password2=NeuesPass123",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 200 and "gespeichert" in r.text
    assert a.get("/api/v1/auth/me").status_code == 401  # old sessions ended
    assert client.post("/api/v1/auth/login", json={"email": a.email, "password": "NeuesPass123"}).status_code == 200
    r = client.post("/api/v1/auth/password-reset/confirm", content=f"token={token}&password=Anders12345x&password2=Anders12345x",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 400  # single use


def test_reset_on_unverified_account_starts_fresh(make_account, client):
    import re
    a = make_account("squat")
    client.post("/api/v1/auth/password-reset", json={"email": a.email})
    token = re.search(r"token=([\w.-]+)", [m for m in get_mailer().sent if m.to == a.email][-1].text).group(1)
    client.post("/api/v1/auth/password-reset/confirm", content=f"token={token}&password=Frisch12345x&password2=Frisch12345x",
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = client.post("/api/v1/auth/login", json={"email": a.email, "password": "Frisch12345x"})
    assert r.status_code == 200 and r.json()["tenant_id"] != a.tenant_id  # squatter's workspace not inherited
