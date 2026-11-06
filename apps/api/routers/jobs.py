"""Job API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

class CreateJobRequest(BaseModel):
    blueprint: dict | None = None
    idempotency_key: str | None = None

class JobResponse(BaseModel):
    id: str
    status: str
    attempt: int
    trace_id: str | None = None

@router.post("", response_model=JobResponse)
def create_job(req: CreateJobRequest):
    # TODO: persist to DB, enqueue worker, quota check
    trace_id = str(uuid.uuid4())[:8]
    job_id = str(uuid.uuid4())
    return JobResponse(id=job_id, status="RECEIVED", attempt=0, trace_id=trace_id)

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    # TODO: DB lookup with tenant scoping
    raise HTTPException(status_code=404, detail="Job not found")

@router.post("/{job_id}/resume")
def resume_job(job_id: str):
    # TODO: validate HITL response, resume LangGraph thread
    return {"status": "resumed", "job_id": job_id}

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    # TODO: idempotent cancel, worker abort
    return {"status": "cancelled", "job_id": job_id}
