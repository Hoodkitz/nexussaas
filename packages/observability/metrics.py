"""Prometheus metrics."""
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter("nexus_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("nexus_http_request_seconds", "HTTP latency", ["method", "route"],
                         buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
RATE_LIMITED = Counter("nexus_rate_limited_total", "Requests rejected by rate limiting", ["scope"])
AUTH_EVENTS = Counter("nexus_auth_events_total", "Auth events", ["event"])
JOBS = Counter("nexus_jobs_total", "Job lifecycle events", ["event"])
JOB_STAGE_SECONDS = Histogram("nexus_job_stage_seconds", "Duration of workflow stages", ["stage"])
SANDBOX_RUNS = Counter("nexus_sandbox_runs_total", "Sandbox executions", ["result"])
WEBHOOKS = Counter("nexus_webhooks_total", "Webhook events", ["provider", "result"])


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
