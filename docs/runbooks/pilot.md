# Pilot (Phase 7)

## Setup
- `PILOT_MODE=true`, `PILOT_ALLOWED_EMAILS=a@x.de,b@y.de`: only listed addresses can register.
  New tenants get status `pilot`. Quotas per plan: free 20 jobs/month, pro 500.
- Every job passes two human gates (blueprint approval, release approval) by an admin/owner.
- Suspend a tenant: set `tenants.status = 'suspended'` (as owner role); new jobs, retries and
  decisions are refused and the worker skips its jobs.

## Monitoring
- `/metrics`: `nexus_jobs_total{event}`, `nexus_job_stage_seconds`, `nexus_sandbox_runs_total`,
  `nexus_http_request_seconds`, `nexus_rate_limited_total`, `nexus_webhooks_total`.
- JSON logs carry `request_id`, `tenant_id`, `trace_id`.

## Exit criteria
- >= 3 pilot tenants, >= 30 completed jobs, 0 cross-tenant incidents.
- Job success rate >= 90 % (excluding rejected), P95 job acceptance < 2 s, P95 sync API < 500 ms.
- Sandbox on gVisor or separate host; email verification live; Stripe live mode tested.
- Restore test done; incident runbook rehearsed once.
