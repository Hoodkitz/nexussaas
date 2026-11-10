"""Worker process: outbox dispatcher, delayed-retry promoter, stale-job reaper, job executor.

Run: python -m apps.worker.main
"""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import time
import uuid
from datetime import datetime, timezone

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import text

from apps.worker.runner import Runner, checkpointer_url
from packages.domain.billing import poll_stripe_events
from packages.observability.logging import setup_logging
from packages.settings import settings
from packages.storage import queue
from packages.storage.db import new_session

log = logging.getLogger("nexus.worker")
_stop = False


def _handle_signal(signum, frame):  # pragma: no cover
    global _stop
    _stop = True


def dispatch_outbox(r, batch: int = 50) -> int:
    """Publish unpublished outbox events to Redis (at-least-once)."""
    db = new_session()
    try:
        rows = db.execute(text(
            "SELECT id, topic, payload FROM outbox_events WHERE published_at IS NULL "
            "ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED"), {"n": batch}).all()
        for row in rows:
            if row.topic == "job.dispatch":
                queue.enqueue(r, row.payload)
            db.execute(text("UPDATE outbox_events SET published_at = :now, attempts = attempts + 1 WHERE id = :id"),
                       {"now": datetime.now(timezone.utc), "id": row.id})
        db.commit()
        return len(rows)
    finally:
        db.close()


def reap_stale(r, older_than: str = "15 minutes") -> int:
    """Re-dispatch jobs stuck in a running state (e.g. lost queue item). Idempotent via checkpoints."""
    db = new_session()
    try:
        rows = db.execute(text("SELECT job_id, tenant_id FROM system_stale_jobs(CAST(:i AS interval))"),
                          {"i": older_than}).all()
    finally:
        db.close()
    for row in rows:
        if not r.exists(queue.LOCK + str(row.job_id)):
            queue.enqueue(r, {"job_id": str(row.job_id), "tenant_id": str(row.tenant_id), "action": "start"})
    return len(rows)


def poll_billing(r) -> None:
    if not settings.STRIPE_SECRET_KEY or settings.STRIPE_WEBHOOK_SECRET:
        return  # webhooks configured (or no Stripe): nothing to poll
    try:
        counts = poll_stripe_events(r, settings.STRIPE_SECRET_KEY)
        if counts:
            log.info("stripe events polled", extra={"fields": counts})
    except Exception:
        log.exception("stripe polling failed")


def process_one(runner: Runner, r, worker_id: str, timeout: float = 2.0) -> dict | None:
    raw = queue.take(r, worker_id, timeout)
    if raw is None:
        return None
    msg = json.loads(raw)
    lock_owner = f"{worker_id}:{uuid.uuid4().hex[:8]}"
    if not queue.acquire_lock(r, msg["job_id"], lock_owner, ttl=settings.SANDBOX_TIMEOUT + 600):
        # Another worker is on this job; retry later instead of running it twice.
        queue.enqueue_delayed(r, msg, 10)
        queue.ack(r, worker_id, raw)
        return {"outcome": "locked"}
    try:
        result = runner.handle(msg)
    except Exception:
        # Unexpected infrastructure error (e.g. DB unavailable): retry later.
        log.exception("job handling crashed", extra={"fields": {"job_id": msg["job_id"]}})
        queue.enqueue_delayed(r, msg, 30)
        queue.ack(r, worker_id, raw)
        queue.release_lock(r, msg["job_id"], lock_owner)
        return {"outcome": "error"}
    # BaseException (process killed / shutting down) skips the ack on purpose: the item
    # stays in this worker's processing list and is recovered once its heartbeat expires.
    if result["outcome"] == "retry":
        queue.enqueue_delayed(r, {**msg, "action": "start", "decision": None}, result["delay"])
    log.info("job processed", extra={"fields": {"job_id": msg["job_id"], **result}})
    queue.ack(r, worker_id, raw)
    queue.release_lock(r, msg["job_id"], lock_owner)
    return result


def main() -> None:  # pragma: no cover - process loop
    setup_logging(settings.LOG_LEVEL)
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    r = queue.client()
    queue.heartbeat(r, worker_id)
    log.info("worker started", extra={"fields": {"worker_id": worker_id, "recovered": queue.recover_orphans(r)}})
    last_maint = 0.0
    last_slow = 0.0
    with PostgresSaver.from_conn_string(checkpointer_url()) as saver:
        runner = Runner(saver)
        while not _stop:
            now = time.time()
            if now - last_maint > 5:
                queue.heartbeat(r, worker_id)
                dispatch_outbox(r)
                queue.promote_delayed(r)
                queue.recover_orphans(r)
                if now - last_slow > 60:
                    reap_stale(r)
                    poll_billing(r)
                    last_slow = now
                last_maint = now
            try:
                if process_one(runner, r, worker_id) is None:
                    dispatch_outbox(r)
            except Exception:
                log.exception("worker loop error")
                time.sleep(1)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
