"""Webhook endpoints."""
from fastapi import APIRouter, Request, HTTPException
import os

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

@router.post("/stripe")
async def stripe_webhook(request: Request):
    # TODO: verify signature, persist event_id (idempotent), enqueue worker
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not sig:
        raise HTTPException(status_code=400, detail="Missing signature")
    return {"status": "received"}
