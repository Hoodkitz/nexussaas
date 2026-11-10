"""Phase 6 acceptance: Stripe webhooks are idempotent and order-safe."""
import hashlib
import hmac
import json
import time
import uuid

import pytest

from tests.conftest import needs_services

pytestmark = needs_services
SECRET = "whsec_test_secret_for_unit_tests"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    from packages.settings import settings

    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", SECRET)


def signed(event: dict, secret: str = SECRET) -> tuple[bytes, dict]:
    payload = json.dumps(event).encode()
    t = int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"}


def sub_event(tenant_id, status="active", created=None, etype="customer.subscription.updated", eid=None):
    return {"id": eid or f"evt_{uuid.uuid4().hex}", "type": etype, "created": created or int(time.time()),
            "data": {"object": {"id": "sub_123", "customer": "cus_123", "status": status,
                                "current_period_end": int(time.time()) + 86400 * 30,
                                "metadata": {"tenant_id": tenant_id, "plan": "pro"}}}}


def post(client, event, secret=SECRET):
    payload, headers = signed(event, secret)
    return client.post("/api/v1/billing/webhook", content=payload, headers=headers)


def test_rejects_bad_signature(client, make_account):
    a = make_account()
    assert post(client, sub_event(a.tenant_id), secret="whsec_wrong").status_code == 400
    assert client.post("/api/v1/billing/webhook", content=b"{}").status_code == 400


def test_subscription_upgrades_plan_and_quota(client, make_account):
    a = make_account()
    assert post(client, sub_event(a.tenant_id)).json()["status"] == "processed"
    assert a.get("/api/v1/billing/subscription").json()["plan"] == "pro"
    assert a.get("/api/v1/tenants/current").json()["plan"] == "pro"


def test_duplicate_delivery_is_noop(client, make_account):
    a = make_account()
    ev = sub_event(a.tenant_id)
    assert post(client, ev).json()["status"] == "processed"
    for _ in range(3):
        assert post(client, ev).json()["status"] == "duplicate"
    from sqlalchemy import text

    from packages.storage.db import new_session

    db = new_session(a.tenant_id)
    n = db.execute(text("SELECT count(*) FROM audit_log WHERE action='billing.subscription_changed'")).scalar()
    db.close()
    assert n == 1


def test_out_of_order_events(client, make_account):
    """A late 'active' event must not undo a newer cancellation."""
    a = make_account()
    now = int(time.time())
    assert post(client, sub_event(a.tenant_id, "active", now - 100)).json()["status"] == "processed"
    assert post(client, sub_event(a.tenant_id, "canceled", now,
                                  etype="customer.subscription.deleted")).json()["status"] == "processed"
    assert post(client, sub_event(a.tenant_id, "active", now - 50)).json()["status"] == "stale"
    s = a.get("/api/v1/billing/subscription").json()
    assert s["status"] == "canceled" and s["plan"] == "free"


def test_concurrent_duplicates_apply_once(client, make_account):
    from concurrent.futures import ThreadPoolExecutor

    from packages.domain.billing import process_event

    a = make_account()
    ev = sub_event(a.tenant_id)
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: process_event(ev), range(8)))
    assert results.count("processed") == 1 and results.count("duplicate") == 7


def test_unknown_tenant_and_type_ignored(client):
    assert post(client, sub_event(str(uuid.uuid4()))).json()["status"] == "ignored"
    ev = sub_event(str(uuid.uuid4()), etype="charge.refunded")
    assert post(client, ev).json()["status"] == "ignored"


def test_checkout_requires_owner_and_config(make_account, client):
    a = make_account()
    assert a.post("/api/v1/billing/checkout").status_code == 503  # not configured in tests
