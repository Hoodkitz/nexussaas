"""Billing: Stripe Checkout and the signed webhook endpoint."""
from __future__ import annotations

import json

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.deps import Principal, require
from packages.domain.billing import process_event
from packages.domain.models import Subscription
from packages.settings import settings

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])
MAX_WEBHOOK_BYTES = 512 * 1024


@router.get("/subscription")
def subscription(p: Principal = Depends(require("read"))):
    s = p.db.get(Subscription, p.tenant_id)
    return {"plan": s.plan, "status": s.status,
            "current_period_end": s.current_period_end} if s else {"plan": "free", "status": "none"}


@router.post("/checkout")
def checkout(p: Principal = Depends(require("billing"))):
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_PRO:
        raise HTTPException(503, "Stripe ist nicht konfiguriert")
    s = p.db.get(Subscription, p.tenant_id)
    params = {
        "mode": "subscription",
        "line_items": [{"price": settings.STRIPE_PRICE_PRO, "quantity": 1}],
        "client_reference_id": str(p.tenant_id),
        "metadata": {"tenant_id": str(p.tenant_id)},
        "subscription_data": {"metadata": {"tenant_id": str(p.tenant_id), "plan": "pro"}},
        "success_url": f"{settings.PUBLIC_BASE_URL}/billing/success",
        "cancel_url": f"{settings.PUBLIC_BASE_URL}/billing/cancel",
    }
    if s and s.stripe_customer_id:
        params["customer"] = s.stripe_customer_id
    else:
        params["customer_email"] = p.user.email
    session = stripe.checkout.Session.create(api_key=settings.STRIPE_SECRET_KEY, **params)
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook-Secret nicht konfiguriert")
    payload = await request.body()
    if len(payload) > MAX_WEBHOOK_BYTES:
        raise HTTPException(413, "Payload zu groß")
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(400, "Signatur fehlt")
    try:
        stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET, tolerance=300)
        event = json.loads(payload)  # verified above
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Ungültige Signatur oder Payload")
    outcome = process_event(event)
    return {"status": outcome}
