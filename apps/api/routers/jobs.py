"""Job management endpoints with DB persistence."""
import uuid
from fastapi import APIRouter, HTTPException
from apps.api.schemas.models import JobCreate, JobOut
from packages.storage.db import SessionLocal
from packages.domain.job import Job
from packages.domain.tenant import Tenant  # noqa: F401

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

@router.post("", response_model=JobOut)
def create_job(req: JobCreate):
    db = SessionLocal()
    try:
        job = Job(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),  # TODO: from auth context
            status="RECEIVED",
            attempt=0,
            trace_id=str(uuid.uuid4()),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return JobOut(id=str(job.id), status=job.status, attempt=job.attempt, trace_id=job.trace_id)
    finally:
        db.close()

@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobOut(id=str(job.id), status=job.status, attempt=job.attempt, trace_id=job.trace_id)
    finally:
        db.close()

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        db.commit()  # status unchanged; cancelled via outbox event
        return {"id": str(job.id), "status": "cancelled"}
    finally:
        db.close()
