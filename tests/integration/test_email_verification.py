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
    assert r.status_code == 200 and r.json()["status"] == "verified"
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
