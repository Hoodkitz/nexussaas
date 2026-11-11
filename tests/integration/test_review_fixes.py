"""Regression tests for review findings: cancelled jobs stay cancelled, tenant cap, draft fallback names."""
from packages.orchestration import jobstore
from tests.integration.test_jobs_flow import _submit


def test_worker_never_overwrites_cancelled_job(make_account):
    a = make_account("cancel")
    jid = _submit(a)
    assert a.post(f"/api/v1/jobs/{jid}/cancel").status_code in (200, 202)
    jobstore.set_status(a.tenant_id, jid, "COMPLETED")  # late write from a worker that was still running
    assert a.get(f"/api/v1/jobs/{jid}").json()["status"] == "CANCELLED"


def test_tenant_creation_is_capped(make_account):
    a = make_account("many")
    codes = [a.post("/api/v1/tenants", json={"name": f"W{i}"}).status_code for i in range(5)]
    assert codes.count(201) == 2 and codes[-1] == 409  # 1 from sign-up + 2 more = 3 owned workspaces


def test_draft_fallback_uses_answer_not_question():
    from apps.api.routers.blueprint import _fallback
    bp = _fallback({"app_description": "Was soll deine App können? → Ein Tool für Vereinsmitglieder"})
    assert bp["name"].startswith("ein_tool") and not bp["description"].startswith("Was soll")
