"""Job persistence helpers used by the worker. All access runs under the job's tenant RLS context."""
from __future__ import annotations

from typing import Any, Optional

from packages.domain.models import Job, JobEvent, JobStatus, OutboxEvent
from packages.storage.db import scoped_session


def get_job(tenant_id: str, job_id: str) -> Optional[Job]:
    with scoped_session(tenant_id) as db:
        return db.get(Job, job_id)


def set_status(tenant_id: str, job_id: str, status: JobStatus | str, detail: Optional[dict] = None,
               **fields: Any) -> None:
    status = getattr(status, "value", status)
    with scoped_session(tenant_id) as db:
        job = db.get(Job, job_id, with_for_update=True)
        if job is None:
            return
        changed = job.status != status
        job.status = status
        for k, v in fields.items():
            setattr(job, k, v)
        if changed or detail:
            db.add(JobEvent(tenant_id=job.tenant_id, job_id=job.id, status=status, detail=detail))


def bump_attempt(tenant_id: str, job_id: str, error: str) -> tuple[int, int]:
    with scoped_session(tenant_id) as db:
        job = db.get(Job, job_id, with_for_update=True)
        job.attempt += 1
        job.error = error[:2000]
        db.add(JobEvent(tenant_id=job.tenant_id, job_id=job.id, status=job.status,
                        detail={"retry": job.attempt, "error": error[:500]}))
        return job.attempt, job.max_attempts


def dispatch(db, job: Job, action: str = "start", decision: Optional[dict] = None) -> None:
    """Enqueue work for a job via the transactional outbox (same transaction as the caller)."""
    db.add(OutboxEvent(topic="job.dispatch", payload={
        "job_id": str(job.id), "tenant_id": str(job.tenant_id), "action": action, "decision": decision,
    }))
