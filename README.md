# NexusSaaS

Multi-tenant SaaS platform that turns an app **blueprint** into a tested, packaged
FastAPI backend through a LangGraph workflow with human approval gates.
Specification: [spec/nexussaas-spec.md](spec/nexussaas-spec.md).

## Status (v0.2.0, 10 Nov 2026)

| Phase | Scope | State |
|---|---|---|
| 0 Decisions | ADRs 01-07 | accepted, implementation notes in `docs/adr` |
| 1 Platform | compose dev stack, FastAPI, Postgres, Redis, object storage, JSON logs, Prometheus metrics, CI | done |
| 2 Identity & tenants | Argon2id login, Google OIDC (code + PKCE), JWT revocation, tenants, RBAC, FORCE RLS | done, cross-tenant tests green |
| 3 Job API + graph | outbox -> Redis queue, worker, LangGraph + Postgres checkpointer, interrupts, retry, cancel | done, crash/resume tests green |
| 4 Synthesis | blueprint validation, DDL with RLS, code generation, static checks, security review, deterministic zip | done, reproducibility test green |
| 5 Sandbox | hardened Docker runner (no network, read-only, cap-drop, non-root, limits) | done, boundary tests green; gVisor/separate host open |
| 6 Billing/ops | Stripe Checkout + idempotent, order-safe webhooks, rate limits, quotas, backup/restore, DSGVO export/erasure | done, duplicate/reorder tests green |
| 7 Pilot | pilot mode with allowlist, quotas, approvals, metrics | ready to start, see `docs/runbooks/pilot.md` |

## Quick start (dev)

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # set SECRET_KEY (>= 32 chars)
make up                         # Postgres + Redis (localhost only)
make migrate                    # schema, app role, RLS, checkpointer tables
make sandbox-image              # image for running generated code
make api                        # http://127.0.0.1:8000/docs
make worker                     # in a second shell
make test                       # 83 tests
```

## Flow

```
POST /api/v1/jobs {blueprint}
  RECEIVED -> SPEC_VALIDATION -> BLUEPRINT_APPROVAL  (POST /jobs/{id}/decision, role admin+)
  -> DDL_GENERATION -> BACKEND_GENERATION -> STATIC_CHECKS -> SANDBOX_TEST -> SECURITY_REVIEW
  -> HUMAN_RELEASE_APPROVAL (decision) -> PACKAGED -> COMPLETED
GET /api/v1/jobs/{id}/artifact        zip with app, SQL migration, tests, manifest, security report
GET /api/v1/jobs/{id}/reports/{static|tests|security|blueprint|ddl}
```

Blueprint example: `tests/fixtures/sample_blueprint.json`. Field types: text, integer, float,
boolean, timestamp, date, uuid, json, email, `ref:<Entity>`; options `required`, `unique`, `max_length`.

## API overview

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/switch-tenant`, `POST /auth/logout-all`, `GET /auth/google`, `GET /auth/google/callback` |
| Tenants | `POST /tenants`, `GET /tenants/current`, `GET/POST /tenants/current/members`, `PATCH/DELETE /tenants/current/members/{user_id}` |
| Jobs | `POST/GET /jobs`, `GET /jobs/{id}`, `/events`, `/decision`, `/cancel`, `/retry`, `/artifact`, `/reports/{name}` |
| Billing | `GET /billing/subscription`, `POST /billing/checkout`, `POST /billing/webhook` |
| Privacy | `GET /users/me/export`, `DELETE /users/me` |
| Ops | `/healthz`, `/readyz`, `/metrics` |

All under `/api/v1` except ops. Roles: owner > admin (approve, members) > member (submit) > viewer (read).

## Layout

```
apps/api        FastAPI app, routers, deps (auth/tenant/RBAC), middleware
apps/worker     queue consumer, outbox dispatcher, reaper, graph runner
packages/       blueprint (schema, ddl, codegen, package), domain, orchestration,
                security, sandbox, storage, observability, settings
migrations/     Alembic (baseline creates app role, RLS, checkpointer tables)
infra/          sandbox image, systemd units
scripts/        backup.sh, restore.sh
docs/           ADRs, runbooks
matrix-app/     Capacitor mobile app (blueprint questionnaire)
```

## Known gaps

- No email delivery yet: password accounts are unverified, so Google login refuses to link to an
  existing unverified password account (fail closed). Needs an email provider for verification and reset.
- Sandbox runs on the same host with runc; production needs gVisor (`SANDBOX_RUNTIME=runsc`) or a
  separate runner host (ADR-04).
- Stripe and Google need real keys (`STRIPE_*`, `GOOGLE_CLIENT_SECRET`) before they work end to end.
- Generated apps use an `X-Tenant-ID` header placeholder that must be replaced by real auth.
