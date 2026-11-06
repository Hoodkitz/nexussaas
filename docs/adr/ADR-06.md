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
