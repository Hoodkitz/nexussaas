"""Executes one queue message against the checkpointed workflow graph."""
from __future__ import annotations

import logging
import traceback

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command

from packages.domain.models import TERMINAL_STATUSES, JobStatus
from packages.observability.logging import tenant_id_var, trace_id_var
from packages.observability.metrics import JOBS
from packages.orchestration import jobstore
from packages.orchestration.graph import JobCancelled, PipelineFailure, build_graph, initial_state
from packages.settings import settings

log = logging.getLogger("nexus.worker")
TERMINAL = {s.value for s in TERMINAL_STATUSES}


def checkpointer_url() -> str:
    return settings.DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")


class Runner:
    def __init__(self, saver: PostgresSaver):
        self.graph = build_graph().compile(checkpointer=saver)

    def handle(self, msg: dict) -> dict:
        """Returns {"outcome": done|waiting|retry|failed|cancelled|skipped, ...}."""
        tenant_id, job_id = msg["tenant_id"], msg["job_id"]
        job = jobstore.get_job(tenant_id, job_id)
        if job is None:
            return {"outcome": "skipped", "reason": "job not found"}
        t1, t2 = tenant_id_var.set(tenant_id), trace_id_var.set(job.trace_id)
        try:
            if job.status in TERMINAL:
                return {"outcome": "skipped", "reason": f"job is {job.status}"}
            if not jobstore.tenant_active(tenant_id):
                return {"outcome": "skipped", "reason": "tenant suspended"}
            config = {"configurable": {"thread_id": job_id}}
            snapshot = self.graph.get_state(config)
            waiting = bool(snapshot.next) and any(t.interrupts for t in snapshot.tasks)
            if msg.get("action") == "resume" and waiting:
                pending = [i.value for t in snapshot.tasks for i in t.interrupts]
                stage = (msg.get("decision") or {}).get("stage")
                if not pending or pending[0].get("stage") != stage:
                    # e.g. a duplicate blueprint approval must not approve the release gate
                    return {"outcome": "skipped", "reason": f"decision for stage {stage} does not match"}
                payload = Command(resume=msg.get("decision") or {})
            elif msg.get("action") == "resume" and not snapshot.next:
                return {"outcome": "skipped", "reason": "nothing to resume"}
            elif snapshot.next:
                if waiting:
                    return {"outcome": "waiting"}
                payload = None  # crashed mid-run: continue from the last checkpoint
                log.info("resuming from checkpoint", extra={"fields": {"job_id": job_id, "next": snapshot.next}})
            elif snapshot.values:
                return {"outcome": "skipped", "reason": "graph already finished"}
            else:
                payload = initial_state(tenant_id, job_id, job.trace_id or job_id)
                JOBS.labels("started").inc()
            try:
                self.graph.invoke(payload, config)
            except JobCancelled:
                JOBS.labels("cancelled").inc()
                return {"outcome": "cancelled"}
            except PipelineFailure as e:
                jobstore.set_status(tenant_id, job_id, JobStatus.FAILED, {"reason": e.reason, **e.detail},
                                    error=e.reason)
                JOBS.labels("failed").inc()
                return {"outcome": "failed", "reason": e.reason}
            except Exception as e:  # transient: retry with backoff
                err = f"{type(e).__name__}: {e}"
                log.warning("job step failed", extra={"fields": {"job_id": job_id, "error": err,
                                                                 "trace": traceback.format_exc()[-1500:]}})
                attempt, max_attempts = jobstore.bump_attempt(tenant_id, job_id, err)
                if attempt >= max_attempts:
                    jobstore.set_status(tenant_id, job_id, JobStatus.FAILED,
                                        {"reason": "retries exhausted", "error": err[:500]}, error=err[:2000])
                    JOBS.labels("failed").inc()
                    return {"outcome": "failed", "reason": "retries exhausted"}
                JOBS.labels("retried").inc()
                return {"outcome": "retry", "delay": min(300, 5 * 2 ** (attempt - 1))}
            snapshot = self.graph.get_state(config)
            if snapshot.next:
                return {"outcome": "waiting"}
            JOBS.labels(snapshot.values.get("status", "done").lower()).inc()
            return {"outcome": "done", "status": snapshot.values.get("status")}
        finally:
            tenant_id_var.reset(t1)
            trace_id_var.reset(t2)
