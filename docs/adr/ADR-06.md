# ADR-06: Idempotente Stripe-Webhook-Verarbeitung

## Status: Accepted

## Kontext
Stripe sendet Events ggf. mehrfach. Nebenwirkungen (Billing, E-Mail) dürfen nicht dupliziert werden.

## Entscheidung
Stripe-Events mit DB-Unique-Key idempotent verarbeiten. Ereignis-ID und Zustandsänderung transaktional.
Externe Nebenwirkungen über Outbox/Worker.

## Konsequenzen
- Event-ID mit UNIQUE constraint
- Schnelle 2xx nach persistierter Annahme
- Verarbeitung asynchron über Worker

## Implementierung (v0.2)
`packages/domain/billing.py`: `INSERT ... ON CONFLICT DO NOTHING` auf `webhook_inbox.event_id` und Zustandsänderung in
einer Transaktion; Abo-Events nur angewendet, wenn `event.created >= last_event_created`.
