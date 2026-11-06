"""Prometheus metrics (stub)."""
METRICS = {
    "jobs_total": 0,
    "jobs_completed": 0,
    "jobs_failed": 0,
    "api_requests_total": 0,
    "sandbox_runs_total": 0,
}

def increment(metric: str, value: int = 1):
    if metric in METRICS:
        METRICS[metric] += value

def get_metrics():
    return METRICS.copy()
