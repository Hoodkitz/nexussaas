# Roadmap

Short roadmap focused on deliverables that help sell NexusSaaS to early customers.

- 0.x: Platform hardening & observability
  - Compose dev stack, FastAPI backend, Postgres, Redis, object storage, JSON logs, Prometheus metrics (done)
- 1.x: Identity & multi-tenancy
  - Argon2id login, Google OIDC, JWT revocation, tenants, RBAC, FORCE RLS (done)
- 2.x: Jobs & graph
  - Outbox -> Redis queue, worker, LangGraph checkpointing, retry/cancel (done)
- 3.x: Synthesis & packaging
  - Blueprint validation, deterministic packaging, static security checks (in progress)
- Sales readiness small items (this PR):
  - Provide a clear Roadmap document for prospective customers (this file)
  - Improve example email sender in .env.example to a professional support address

Generated: 2026-11-12T20:29:18.887463Z

## Sales readiness checklist

Small verifiable items to present to early customers:

- Improve example outbound mail sender in .env.example to a professional support address (updated in this PR).
- Provide a concise Roadmap + contact placeholders for pilot and sales queries (this file).

## Contact

For pilot inquiries (early access, evaluation): pilot@nexussaas.example
For sales and partnerships: sales@nexussaas.example
For support and operations questions: support@nexussaas.example

Generated: 2026-11-13T07:42:53.435494Z
