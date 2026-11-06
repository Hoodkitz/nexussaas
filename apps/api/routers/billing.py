"""Stripe billing webhook handler."""
import os
try:
    import stripe
except ImportError:
    stripe = None
from fastapi import APIRouter, Request, HTTPException
from packages.domain.webhook_inbox import WebhookInbox
from packages.storage.outbox import OutboxEvent
import json
from packages.storage.db import SessionLocal

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Idempotent: check if already processed
    db = SessionLocal()
    try:
        existing = db.query(WebhookInbox).filter(WebhookInbox.event_id == event["id"]).first()
        if existing:
            return {"status": "already_processed"}
        inbox = WebhookInbox(
            event_id=event["id"],
            event_type=event["type"],
            payload=event["data"]["object"],
            status="pending",
        )
        db.add(inbox)
        db.commit()
    finally:
        db.close()

    # Enqueue processing via outbox
    db = SessionLocal()
    try:
        outbox = OutboxEvent(
            aggregate_type="stripe_webhook",
            aggregate_id=event["id"],
            event_type=event["type"],
            payload=event["data"]["object"],
            idempotency_key=event["id"],
        )
        db.add(outbox)
        db.commit()
    finally:
        db.close()
    return {"status": "received"}
