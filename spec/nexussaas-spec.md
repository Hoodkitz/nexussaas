# NexusSaaS — Gesamtspezifikation & Entwickler-Handoff

**Version 1.0 · 6. November 2026**

Vollständige Spezifikation siehe PDF: `nexussaas-spec.pdf`

## Zusammenfassung

Modulare SaaS-Plattform mit KI-Agenten-Orchestrierung. Konsolidierte technische
Spezifikation aus Konzept/Blueprint und Vollständigkeitsprüfung.

## Architekturentscheidungen (ADRs)

| ID | Entscheidung | Begründung |
|---|---|---|
| ADR-01 | Modularer Backend-Service + separater Worker/Orchestrator (MVP) | Agenten als Graph-Nodes; Microservices erst bei Skalierungsbedarf |
| ADR-02 | LangGraph für zustandsbehaftete Agentenabläufe; PostgreSQL als Checkpointer | Interrupts/Wiederaufnahme brauchen Checkpointer + stabile thread_id |
| ADR-03 | Große Artefakte in Object Storage, nicht in Graph-State | State speichert IDs/URIs/Hashes |
| ADR-04 | Untrusted Code in separater Sandbox (gVisor/MicroVM) | Container allein keine starke Grenze |
| ADR-05 | PostgreSQL RLS ergänzt Applikationsautorisierung | Tenant-ID in Tabellen, Default-Deny |
| ADR-06 | Stripe-Events idempotent (DB-Unique-Key) | Ereignis-ID + Zustandsänderung transaktional |
| ADR-07 | Art. 17 ≠ Soft-Delete | Löschung/Anonymisierung gesondert behandeln |

## Stack

- Web/API: FastAPI, Auth/OIDC, REST, RBAC, Tenant Context
- Orchestrator: LangGraph, PostgreSQL Checkpointer, Model/Tool Adapters
- Worker: Async Generation, Test, Scanning, Packaging, Webhooks
- Data: PostgreSQL (RLS), Redis (Cache/Rate-Limit/Queue), Object Storage
- Sandbox: Separate Host, gVisor/MicroVM, keine Docker-Socket-Mounts

## Workflow-Zustände

RECEIVED → SPEC_VALIDATION → BLUEPRINT_APPROVAL → DDL_GENERATION → BACKEND_GENERATION → STATIC_CHECKS → SANDBOX_TEST → SECURITY_REVIEW → HUMAN_RELEASE_APPROVAL → PACKAGED → COMPLETED

## Wichtige Korrekturen

1. **OAuth2 Password Flow: MUST NOT** (RFC 9700) → Authorization Code + PKCE
2. **Soft-Delete ≠ Art. 17** Erfüllung
3. **Docker --rm ≠ Sicherheitsgarantie**
4. **"Deterministisch"** bezieht sich auf Kontrollfluss, nicht LLM-Ausgaben
5. **"Enterprise-ready"** nicht ohne Tests/Compliance-Review behaupten

## Umsetzungsplan (8 Phasen)

| Phase | Umfang | Abnahme |
|---|---|---|
| 0 – Entscheidungen | Use cases, Threat Model, Tenant Model, IDP, Sandbox, Object Store | ADRs akzeptiert |
| 1 – Plattformgrundlage | Repo/CI, FastAPI, PostgreSQL, Redis, Observability | Deploybar in dev |
| 2 – Identity & Tenants | OIDC, RBAC, RLS, API Authorization | Cross-tenant tests grün |
| 3 – Job API + Graph | Jobs, Queue, Checkpointer, Retry | Crash/resume tests grün |
| 4 – Synthesis Pipeline | Blueprint, DDL, Code Gen, Tests, Scanner | Reproducible outputs |
| 5 – Sandbox | Separate Runner, Hardened Profiles, Network Deny | Boundary tests |
| 6 – Billing/Operations | Stripe Webhooks, Rate Limiting, Backup/Restore | Duplicate/reorder tests |
| 7 – Pilot | Limited Tenants, Human Approval, Monitoring | Pilot exit criteria |

## Repo-Struktur

```
nexussaas/
├── apps/api/          # FastAPI routes, dependencies
├── apps/worker/       # queue consumers, scheduled jobs
├── packages/domain/   # entities, policies, interfaces
├── packages/blueprint/ # JSON Schema + validators
├── packages/orchestration/ # LangGraph state, nodes
├── packages/security/  # auth, tenant context, audit
├── packages/sandbox/   # runner client
├── packages/storage/   # PostgreSQL, object storage, Redis
├── migrations/         # Alembic + RLS policies
├── infra/             # IaC, deployment
├── tests/             # unit, integration, security, e2e
├── docs/adr/          # Architecture Decision Records
└── docs/runbooks/     # Operational runbooks
```

## NFRs (MVP-Zielwerte)

- API-Latenz: P95 < 500ms (synchrone Routen)
- Jobannahme: < 2s P95
- Tenant-Sicherheit: Cross-tenant Zugriff immer verweigert
- Sandbox: Kein Netzwerk-Egress ohne Allowlist
- Kosten: Per-tenant quotas, per-job token/call caps

## Quelle

PDF: `aaaas.pdf` — NexusSaaS Gesamtspezifikation & Entwickler-Handoff v1.0, 6. Nov 2026
