"""Stripe event processing (ADR-06): idempotent by event id, order-safe by event.created.

The inbox row (unique event_id) and the subscription change are written in ONE
transaction, so a crash can never mark an event processed without applying it,
and a redelivered event is a no-op.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from packages.domain.models import Subscription, Tenant, WebhookInbox
from packages.observability.metrics import WEBHOOKS
from packages.security.audit import audit
from packages.storage.db import new_session, set_context

log = logging.getLogger("nexus.billing")

PLAN_QUOTAS = {"free": 20, "pro": 500}
ACTIVE = {"active", "trialing"}
HANDLED = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


def _tenant_for(db, obj: dict) -> Optional[str]:
    meta = obj.get("metadata") or {}
    tid = meta.get("tenant_id") or obj.get("client_reference_id")
    if not tid and obj.get("customer"):
        tid = db.execute(text("SELECT system_tenant_for_customer(:c)"), {"c": obj["customer"]}).scalar()
    try:
        return str(uuid.UUID(str(tid))) if tid else None
    except ValueError:
        return None


def _plan_for(obj: dict) -> str:
    meta = obj.get("metadata") or {}
    return meta.get("plan") if meta.get("plan") in PLAN_QUOTAS else "pro"


def process_event(event: dict) -> str:
    """Returns processed | duplicate | ignored | stale."""
    db = new_session()
    try:
        inserted = db.execute(
            insert(WebhookInbox).values(
                id=uuid.uuid4(), provider="stripe", event_id=event["id"], event_type=event["type"],
                event_created=int(event.get("created") or 0), status="pending",
                payload={"type": event["type"], "object_id": event["data"]["object"].get("id")},
            ).on_conflict_do_nothing(index_elements=["event_id"]).returning(WebhookInbox.id)
        ).scalar()
        if inserted is None:
            db.rollback()
            WEBHOOKS.labels("stripe", "duplicate").inc()
            return "duplicate"
        outcome = _apply(db, event)
        db.execute(text("UPDATE webhook_inbox SET status = :s, processed_at = :t, attempts = attempts + 1 "
                        "WHERE event_id = :e"),
                   {"s": "processed" if outcome == "processed" else outcome,
                    "t": datetime.now(timezone.utc), "e": event["id"]})
        db.commit()
        WEBHOOKS.labels("stripe", outcome).inc()
        return outcome
    except Exception:
        db.rollback()
        WEBHOOKS.labels("stripe", "error").inc()
        raise
    finally:
        db.close()


def _apply(db, event: dict) -> str:
    etype, obj = event["type"], event["data"]["object"]
    if etype not in HANDLED:
        return "ignored"
    tenant_id = _tenant_for(db, obj)
    if tenant_id is None:
        log.warning("stripe event without tenant", extra={"fields": {"event_id": event["id"], "type": etype}})
        return "ignored"
    set_context(db, tenant_id)
    sub = db.get(Subscription, uuid.UUID(tenant_id), with_for_update=True)
    tenant = db.get(Tenant, uuid.UUID(tenant_id), with_for_update=True)
    if sub is None or tenant is None:
        return "ignored"
    created = int(event.get("created") or 0)

    if etype == "checkout.session.completed":
        # Only links the customer; plan state comes from subscription events.
        sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
        if obj.get("subscription"):
            sub.stripe_subscription_id = obj["subscription"]
        audit(db, tenant.id, None, "billing.checkout_completed", event["id"])
        return "processed"

    if etype == "invoice.payment_failed":
        audit(db, tenant.id, None, "billing.payment_failed", event["id"])
        return "processed"

    # Subscription lifecycle: apply only if newer than what we have (out-of-order safe).
    if created < sub.last_event_created:
        audit(db, tenant.id, None, "billing.stale_event_skipped", event["id"], {"type": etype})
        return "stale"
    status = "canceled" if etype == "customer.subscription.deleted" else obj.get("status", "active")
    sub.status = status
    sub.stripe_subscription_id = obj.get("id") or sub.stripe_subscription_id
    sub.stripe_customer_id = obj.get("customer") or sub.stripe_customer_id
    if obj.get("current_period_end"):
        sub.current_period_end = datetime.fromtimestamp(int(obj["current_period_end"]), tz=timezone.utc)
    sub.last_event_created = created
    plan = _plan_for(obj) if status in ACTIVE else "free"
    sub.plan = plan
    tenant.plan = plan
    tenant.monthly_job_quota = PLAN_QUOTAS[plan]
    audit(db, tenant.id, None, "billing.subscription_changed", event["id"], {"status": status, "plan": plan})
    return "processed"
