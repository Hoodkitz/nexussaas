# Incident Response Runbook

## Detection
- Alerts via observability (Prometheus/Grafana)
- Error rate spike, latency degradation, tenant isolation breach

## Classification
1. P1: Data breach / tenant isolation failure → immediate containment
2. P2: Service degradation > 50% → scale + investigate
3. P3: Single tenant issue → investigate + communicate
4. P4: Non-critical bug → track + fix in next release

## Response Steps
1. Acknowledge alert
2. Assess scope (affected tenants, data exposure)
3. Contain (kill switch, rate limit, disable feature)
4. Investigate (logs, traces, DB queries)
5. Fix + deploy
6. Post-mortem within 48h

## Contacts
- On-call: TBD
- Security: TBD
- DPO: TBD
