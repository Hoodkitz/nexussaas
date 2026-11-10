"""Job API: submit blueprints, follow progress, human approvals, artifacts."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func

from apps.api.deps import Principal, require
from apps.api.schemas.models import JobCreate, JobDecisionIn, JobOut
from packages.blueprint.schema import validate_blueprint
from packages.domain.models import APPROVAL_STATUSES, TERMINAL_STATUSES, Job, JobEvent, JobStatus, Tenant
from packages.observability.metrics import JOBS
from packages.orchestration.jobstore import dispatch
from packages.security.audit import audit
from packages.settings import settings
from packages.storage.object_storage import get_storage

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
REPORTS = {"static": "static_report.json", "tests": "test_result.json", "security": "security_report.json",
           "blueprint": "blueprint.normalized.json", "ddl": "schema.sql"}
MAX_BLUEPRINT_BYTES = 256 * 1024


def _out(j: Job) -> JobOut:
    return JobOut(id=str(j.id), status=j.status, attempt=j.attempt, trace_id=j.trace_id,
                  artifact_sha256=j.artifact_sha256, result=j.result, error=j.error,
                  created_at=j.created_at, updated_at=j.updated_at)


def _job(p: Principal, job_id: str, lock: bool = False) -> Job:
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Job nicht gefunden")
    job = p.db.get(Job, jid, with_for_update=lock)  # RLS: other tenants' jobs are invisible
    if job is None:
        raise HTTPException(404, "Job nicht gefunden")
    return job


MAX_MANUAL_RETRIES = 3


def _active_tenant(p: Principal, lock: bool = False) -> Tenant:
    """Every path that dispatches work must pass this gate."""
    tenant = p.db.get(Tenant, p.tenant_id, with_for_update=lock)
    if tenant is None or tenant.status not in ("active", "pilot"):
        raise HTTPException(403, "Tenant ist gesperrt")
    return tenant


@router.post("", response_model=JobOut, status_code=201)
def create_job(req: JobCreate, response: Response, p: Principal = Depends(require("write")),
               idempotency_key: Optional[str] = Header(default=None, max_length=255)):
    key = idempotency_key or req.idempotency_key
    if key:
        existing = p.db.query(Job).filter(Job.tenant_id == p.tenant_id, Job.idempotency_key == key).one_or_none()
        if existing:
            response.status_code = status.HTTP_200_OK
            return _out(existing)
    if len(json.dumps(req.blueprint)) > MAX_BLUEPRINT_BYTES:
        raise HTTPException(413, "Blueprint zu groß")
    ok, errors = validate_blueprint(req.blueprint)
    if not ok:
        raise HTTPException(422, detail={"blueprint_errors": errors})
    # Row lock serializes concurrent submissions per tenant, so the quota check is exact.
    tenant = _active_tenant(p, lock=True)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = p.db.query(func.count(Job.id)).filter(Job.tenant_id == p.tenant_id,
                                                 Job.created_at >= month_start).scalar()
    if used >= tenant.monthly_job_quota:
        raise HTTPException(429, f"Monatskontingent erreicht ({tenant.monthly_job_quota} Jobs)")
    job = Job(id=uuid.uuid4(), tenant_id=p.tenant_id, created_by=p.user_id, status=JobStatus.RECEIVED.value,
              blueprint=req.blueprint, idempotency_key=key, attempt=0, max_attempts=settings.JOB_MAX_ATTEMPTS,
              trace_id=uuid.uuid4().hex)
    p.db.add(job)
    p.db.flush()
    p.db.add(JobEvent(tenant_id=p.tenant_id, job_id=job.id, status=job.status, actor_id=p.user_id))
    dispatch(p.db, job, "start")
    audit(p.db, p.tenant_id, p.user_id, "job.created", str(job.id))
    JOBS.labels("created").inc()
    return _out(job)


@router.get("", response_model=list[JobOut])
def list_jobs(p: Principal = Depends(require("read")), limit: int = Query(50, ge=1, le=200),
              offset: int = Query(0, ge=0), status_filter: Optional[str] = Query(None, alias="status")):
    q = p.db.query(Job).filter(Job.tenant_id == p.tenant_id)
    if status_filter:
        q = q.filter(Job.status == status_filter)
    return [_out(j) for j in q.order_by(Job.created_at.desc()).offset(offset).limit(limit)]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, p: Principal = Depends(require("read"))):
    return _out(_job(p, job_id))


@router.get("/{job_id}/events")
def job_events(job_id: str, p: Principal = Depends(require("read"))):
    job = _job(p, job_id)
    rows = p.db.query(JobEvent).filter(JobEvent.job_id == job.id).order_by(JobEvent.id).all()
    return [{"status": e.status, "detail": e.detail, "actor_id": str(e.actor_id) if e.actor_id else None,
             "at": e.created_at} for e in rows]


@router.post("/{job_id}/decision", response_model=JobOut)
def decide(job_id: str, req: JobDecisionIn, p: Principal = Depends(require("approve"))):
    """Human approval gate (blueprint approval and release approval)."""
    _active_tenant(p)
    job = _job(p, job_id, lock=True)
    if job.status not in {s.value for s in APPROVAL_STATUSES}:
        raise HTTPException(409, f"Job wartet nicht auf eine Freigabe (Status {job.status})")
    stage = "blueprint" if job.status == JobStatus.BLUEPRINT_APPROVAL.value else "release"
    decision = {"stage": stage, "approve": req.approve, "actor": str(p.user_id), "comment": req.comment,
                "at": datetime.now(timezone.utc).isoformat()}
    p.db.add(JobEvent(tenant_id=p.tenant_id, job_id=job.id, status=job.status, actor_id=p.user_id,
                      detail={"decision": "approved" if req.approve else "rejected", "stage": stage,
                              "comment": req.comment}))
    dispatch(p.db, job, "resume", decision)
    audit(p.db, p.tenant_id, p.user_id, f"job.{stage}_{'approved' if req.approve else 'rejected'}", str(job.id))
    return _out(job)


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: str, p: Principal = Depends(require("write"))):
    job = _job(p, job_id, lock=True)
    if job.status in {s.value for s in TERMINAL_STATUSES}:
        raise HTTPException(409, f"Job ist bereits beendet ({job.status})")
    job.status = JobStatus.CANCELLED.value
    p.db.add(JobEvent(tenant_id=p.tenant_id, job_id=job.id, status=job.status, actor_id=p.user_id))
    audit(p.db, p.tenant_id, p.user_id, "job.cancelled", str(job.id))
    return _out(job)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry(job_id: str, p: Principal = Depends(require("write"))):
    _active_tenant(p)
    job = _job(p, job_id, lock=True)
    if job.status != JobStatus.FAILED.value:
        raise HTTPException(409, "Nur fehlgeschlagene Jobs können neu gestartet werden")
    retries = (p.db.query(func.count(JobEvent.id))
               .filter(JobEvent.job_id == job.id, JobEvent.detail["manual_retry"].astext == "true").scalar())
    if retries >= MAX_MANUAL_RETRIES:
        raise HTTPException(429, f"Maximal {MAX_MANUAL_RETRIES} manuelle Neustarts pro Job")
    job.status, job.attempt, job.error = JobStatus.RECEIVED.value, 0, None
    p.db.add(JobEvent(tenant_id=p.tenant_id, job_id=job.id, status=job.status, actor_id=p.user_id,
                      detail={"manual_retry": True}))
    dispatch(p.db, job, "start")
    audit(p.db, p.tenant_id, p.user_id, "job.retried", str(job.id))
    return _out(job)


@router.get("/{job_id}/artifact")
def artifact(job_id: str, p: Principal = Depends(require("read"))):
    job = _job(p, job_id)
    if job.status != JobStatus.COMPLETED.value or not job.artifact_ref:
        raise HTTPException(409, "Artefakt ist noch nicht verfügbar")
    if not job.artifact_ref.startswith(f"tenants/{p.tenant_id}/"):
        raise HTTPException(404, "Nicht gefunden")
    data = get_storage().get(job.artifact_ref)
    name = job.artifact_ref.rsplit("/", 1)[-1]
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{name}"', "X-Artifact-SHA256": job.artifact_sha256 or ""})


@router.get("/{job_id}/reports/{name}")
def report(job_id: str, name: str, p: Principal = Depends(require("read"))):
    if name not in REPORTS:
        raise HTTPException(404, "Unbekannter Bericht")
    job = _job(p, job_id)
    key = f"tenants/{p.tenant_id}/jobs/{job.id}/{REPORTS[name]}"
    storage = get_storage()
    if not storage.exists(key):
        raise HTTPException(404, "Bericht noch nicht vorhanden")
    media = "application/sql" if name == "ddl" else "application/json"
    return Response(storage.get(key), media_type=media)
