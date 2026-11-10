"""Phase 3/4 acceptance: job API + worker + graph, approvals, crash/resume, retry, reproducibility."""
import io
import json
import uuid
import zipfile

import pytest

from tests.conftest import PASSWORD, needs_services

pytestmark = needs_services

BLUEPRINT = {
    "name": "Task Flow", "version": "1.0", "description": "Aufgaben im Team",
    "entities": [
        {"name": "Project", "fields": [{"name": "title", "type": "text", "required": True}]},
        {"name": "Task", "fields": [{"name": "title", "type": "text", "required": True},
                                    {"name": "done", "type": "boolean"},
                                    {"name": "project_id", "type": "ref:Project"}]},
    ],
}


@pytest.fixture
def worker(monkeypatch):
    """Runs the real worker loop functions in-process against Postgres/Redis."""
    from langgraph.checkpoint.postgres import PostgresSaver

    from apps.worker import main as wm
    from apps.worker.runner import Runner, checkpointer_url
    from packages.storage import queue

    r = queue.client()
    wid = f"test-{uuid.uuid4().hex[:6]}"
    queue.heartbeat(r, wid, ttl=300)
    with PostgresSaver.from_conn_string(checkpointer_url()) as saver:
        runner = Runner(saver)

        class W:
            redis = r
            worker_id = wid

            def drain(self, max_steps=50):
                results = []
                for _ in range(max_steps):
                    wm.dispatch_outbox(r)
                    res = wm.process_one(runner, r, wid, timeout=0.2)
                    if res is None:
                        break
                    results.append(res)
                return results

        yield W()


def _submit(acc, bp=None, **kw):
    r = acc.post("/api/v1/jobs", json={"blueprint": bp or BLUEPRINT}, **kw)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _status(acc, jid):
    return acc.get(f"/api/v1/jobs/{jid}").json()["status"]


def _approve(acc, jid, approve=True):
    r = acc.post(f"/api/v1/jobs/{jid}/decision", json={"approve": approve, "comment": "ok"})
    assert r.status_code == 200, r.text


def test_full_pipeline_with_approvals(make_account, worker):
    a = make_account("owner")
    jid = _submit(a)
    worker.drain()
    assert _status(a, jid) == "BLUEPRINT_APPROVAL"
    _approve(a, jid)
    worker.drain()
    assert _status(a, jid) == "HUMAN_RELEASE_APPROVAL"
    tests = a.get(f"/api/v1/jobs/{jid}/reports/tests").json()
    assert tests["status"] == "passed" and tests["profile"]["network"] == "none"
    _approve(a, jid)
    worker.drain()
    job = a.get(f"/api/v1/jobs/{jid}").json()
    assert job["status"] == "COMPLETED" and len(job["artifact_sha256"]) == 64
    r = a.get(f"/api/v1/jobs/{jid}/artifact")
    assert r.status_code == 200 and r.headers["X-Artifact-SHA256"] == job["artifact_sha256"]
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "task_flow/app/routes.py" in names and "task_flow/MANIFEST.json" in names
    statuses = [e["status"] for e in a.get(f"/api/v1/jobs/{jid}/events").json()]
    for s in ["RECEIVED", "SPEC_VALIDATION", "BLUEPRINT_APPROVAL", "DDL_GENERATION", "BACKEND_GENERATION",
              "STATIC_CHECKS", "SANDBOX_TEST", "SECURITY_REVIEW", "HUMAN_RELEASE_APPROVAL", "PACKAGED", "COMPLETED"]:
        assert s in statuses


def test_reproducible_artifacts(make_account, worker):
    a = make_account()
    shas = []
    for _ in range(2):
        jid = _submit(a)
        worker.drain(); _approve(a, jid); worker.drain(); _approve(a, jid); worker.drain()
        shas.append(a.get(f"/api/v1/jobs/{jid}").json()["artifact_sha256"])
    assert shas[0] == shas[1]


def test_rejection(make_account, worker):
    a = make_account()
    jid = _submit(a)
    worker.drain()
    _approve(a, jid, approve=False)
    worker.drain()
    assert _status(a, jid) == "REJECTED"
    assert a.post(f"/api/v1/jobs/{jid}/decision", json={"approve": True}).status_code == 409


def test_invalid_blueprint_rejected_at_api(make_account):
    a = make_account()
    r = a.post("/api/v1/jobs", json={"blueprint": {"name": "x", "entities": [{"name": "class"}]}})
    assert r.status_code == 422 and r.json()["detail"]["blueprint_errors"]


def test_idempotency_key(make_account):
    a = make_account()
    j1 = _submit(a, headers={"Idempotency-Key": "abc-1"})
    r = a.post("/api/v1/jobs", json={"blueprint": BLUEPRINT}, headers={"Idempotency-Key": "abc-1"})
    assert r.status_code == 200 and r.json()["id"] == j1


def test_member_cannot_approve_viewer_cannot_submit(make_account, client):
    a, m, v = make_account("o"), make_account("m"), make_account("v")
    a.post("/api/v1/tenants/current/members", json={"email": m.email, "role": "member"})
    a.post("/api/v1/tenants/current/members", json={"email": v.email, "role": "viewer"})

    def login(acc):
        t = client.post("/api/v1/auth/login",
                        json={"email": acc.email, "password": PASSWORD, "tenant_id": a.tenant_id}).json()
        return {"Authorization": f"Bearer {t['access_token']}"}

    hm, hv = login(m), login(v)
    assert client.post("/api/v1/jobs", headers=hv, json={"blueprint": BLUEPRINT}).status_code == 403
    r = client.post("/api/v1/jobs", headers=hm, json={"blueprint": BLUEPRINT})
    assert r.status_code == 201
    jid = r.json()["id"]
    assert client.post(f"/api/v1/jobs/{jid}/decision", headers=hm, json={"approve": True}).status_code == 403
    assert client.get(f"/api/v1/jobs/{jid}", headers=hv).status_code == 200


def test_cross_tenant_job_access_denied(make_account, worker):
    a, b = make_account("a"), make_account("b")
    jid = _submit(a)
    worker.drain()
    for path in ["", "/events", "/artifact", "/reports/blueprint"]:
        assert b.get(f"/api/v1/jobs/{jid}{path}").status_code == 404
    assert b.post(f"/api/v1/jobs/{jid}/decision", json={"approve": True}).status_code == 404
    assert b.post(f"/api/v1/jobs/{jid}/cancel").status_code == 404
    assert b.get("/api/v1/jobs").json() == []


def test_cancel(make_account, worker):
    a = make_account()
    jid = _submit(a)
    worker.drain()
    assert a.post(f"/api/v1/jobs/{jid}/cancel").json()["status"] == "CANCELLED"
    assert a.post(f"/api/v1/jobs/{jid}/decision", json={"approve": True}).status_code == 409
    worker.drain()
    assert _status(a, jid) == "CANCELLED"


def test_crash_and_resume_from_checkpoint(make_account, worker, monkeypatch):
    """A worker crash in the middle of the graph resumes from the last checkpoint."""
    from packages.orchestration import graph as g

    a = make_account()
    jid = _submit(a)
    worker.drain()
    _approve(a, jid)

    calls = {"ddl": 0}
    real_static = g.run_static_checks

    def crashing_static(files):
        raise SystemExit("simulated worker crash")  # not caught by the runner, like a killed process

    monkeypatch.setattr(g, "run_static_checks", crashing_static)
    real_ddl = g.generate_ddl

    def counting_ddl(bp):
        calls["ddl"] += 1
        return real_ddl(bp)

    monkeypatch.setattr(g, "generate_ddl", counting_ddl)
    with pytest.raises(SystemExit):
        worker.drain()
    assert _status(a, jid) == "STATIC_CHECKS"
    # The queue item is still in the dead worker's processing list -> recovered.
    from packages.storage import queue

    worker.redis.delete(queue.HEARTBEAT + worker.worker_id)
    worker.redis.delete(queue.LOCK + jid)
    assert queue.recover_orphans(worker.redis) >= 1
    queue.heartbeat(worker.redis, worker.worker_id, ttl=300)
    monkeypatch.setattr(g, "run_static_checks", real_static)
    worker.drain()
    assert _status(a, jid) == "HUMAN_RELEASE_APPROVAL"
    assert calls["ddl"] == 1  # DDL step was not re-executed after the crash


def test_transient_error_retries_then_fails(make_account, worker, monkeypatch):
    from packages.orchestration import graph as g
    from packages.storage import queue

    a = make_account()
    jid = _submit(a)
    worker.drain()
    _approve(a, jid)

    def flaky(files):
        raise ConnectionError("sandbox host unreachable")

    monkeypatch.setattr(g.SandboxClient, "run_tests", lambda self, files: flaky(files))
    for _ in range(3):
        worker.drain()
        # promote delayed retries immediately
        for item in worker.redis.zrange(queue.DELAYED, 0, -1):
            if jid in item:
                worker.redis.zrem(queue.DELAYED, item)
                worker.redis.lpush(queue.READY, item)
    job = a.get(f"/api/v1/jobs/{jid}").json()
    assert job["status"] == "FAILED" and job["attempt"] == 3 and "unreachable" in job["error"]
    monkeypatch.undo()
    assert a.post(f"/api/v1/jobs/{jid}/retry").status_code == 200
    worker.drain()
    assert _status(a, jid) == "HUMAN_RELEASE_APPROVAL"


def test_quota(make_account, monkeypatch):
    a = make_account()
    from packages.domain.models import Tenant
    from packages.storage.db import scoped_session

    with scoped_session(a.tenant_id) as db:
        db.get(Tenant, uuid.UUID(a.tenant_id)).monthly_job_quota = 1
    _submit(a)
    assert a.post("/api/v1/jobs", json={"blueprint": BLUEPRINT}).status_code == 429


def test_job_state_holds_only_refs(make_account, worker):
    """ADR-03: checkpoints store keys and small summaries, not generated code."""
    a = make_account()
    jid = _submit(a)
    worker.drain(); _approve(a, jid); worker.drain()
    from sqlalchemy import text

    from packages.storage.db import engine

    with engine.connect() as c:
        size = c.execute(text("SELECT coalesce(sum(length(blob)),0) FROM checkpoint_blobs WHERE thread_id=:t"),
                         {"t": jid}).scalar()
    assert size < 20000
    state = json.dumps(a.get(f"/api/v1/jobs/{jid}").json())
    assert "def create_" not in state


def test_duplicate_blueprint_approval_does_not_release(make_account, worker):
    a = make_account()
    jid = _submit(a)
    worker.drain()
    _approve(a, jid)
    _approve(a, jid)  # double click before the worker ran
    worker.drain()
    assert _status(a, jid) == "HUMAN_RELEASE_APPROVAL"
