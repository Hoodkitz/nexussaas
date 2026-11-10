"""Synthesis workflow as a LangGraph StateGraph with PostgreSQL checkpointing (ADR-02).

RECEIVED -> SPEC_VALIDATION -> BLUEPRINT_APPROVAL (human) -> DDL_GENERATION ->
BACKEND_GENERATION -> STATIC_CHECKS -> SANDBOX_TEST -> SECURITY_REVIEW ->
HUMAN_RELEASE_APPROVAL (human) -> PACKAGED -> COMPLETED

"Deterministic" refers to the control flow and to the template generators; every
node is idempotent (artifacts live at fixed keys), so a crashed run can resume
from the last checkpoint and re-execute the interrupted node safely.
"""
from __future__ import annotations

import json
import time
from typing import Callable

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from packages.blueprint.codegen import GENERATOR_VERSION, generate_backend
from packages.blueprint.ddl import generate_ddl
from packages.blueprint.package import build_zip, manifest
from packages.blueprint.schema import BlueprintError, normalize_blueprint
from packages.domain.models import JobStatus
from packages.observability.metrics import JOB_STAGE_SECONDS
from packages.orchestration import jobstore
from packages.orchestration.state import WorkflowState
from packages.sandbox.client import SandboxClient
from packages.security.scanner import security_review as run_security_review
from packages.security.scanner import static_checks as run_static_checks
from packages.settings import settings
from packages.storage.object_storage import get_storage

WORKFLOW_VERSION = "1.0"


class PipelineFailure(Exception):
    """Deterministic failure: retrying would give the same result."""

    def __init__(self, reason: str, detail: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


class JobCancelled(Exception):
    pass


def _key(state: WorkflowState, name: str) -> str:
    return f"tenants/{state['tenant_id']}/jobs/{state['job_id']}/{name}"


def _put_json(state: WorkflowState, name: str, obj) -> str:
    key = _key(state, name)
    get_storage().put(key, json.dumps(obj, indent=2, sort_keys=True).encode(), "application/json")
    return key


def _get_json(key: str):
    return json.loads(get_storage().get(key))


def _stage(status: JobStatus) -> Callable:
    """Wrap a node: cancellation check, DB status update, timing."""
    def deco(fn):
        def node(state: WorkflowState) -> dict:
            job = jobstore.get_job(state["tenant_id"], state["job_id"])
            if job is None or job.status == JobStatus.CANCELLED.value:
                raise JobCancelled()
            jobstore.set_status(state["tenant_id"], state["job_id"], status)
            start = time.monotonic()
            try:
                out = fn(state) or {}
            finally:
                JOB_STAGE_SECONDS.labels(status.value).observe(time.monotonic() - start)
            return {"status": status.value, **out}
        node.__name__ = fn.__name__
        return node
    return deco


@_stage(JobStatus.SPEC_VALIDATION)
def validate_spec(state: WorkflowState) -> dict:
    job = jobstore.get_job(state["tenant_id"], state["job_id"])
    try:
        bp = normalize_blueprint(job.blueprint)
    except BlueprintError as e:
        raise PipelineFailure("Blueprint ungültig", {"errors": e.errors})
    summary = {"app": bp["name"], "version": bp["version"],
               "entities": {e["table"]: [f["name"] for f in e["fields"]] for e in bp["entities"]}}
    return {"blueprint_ref": _put_json(state, "blueprint.normalized.json", bp), "summary": summary}


@_stage(JobStatus.BLUEPRINT_APPROVAL)
def blueprint_approval(state: WorkflowState) -> dict:
    decision = interrupt({"stage": "blueprint", "summary": state.get("summary")})
    return {"decisions": [*state.get("decisions", []), {"stage": "blueprint", **decision}]}


@_stage(JobStatus.DDL_GENERATION)
def ddl_generation(state: WorkflowState) -> dict:
    bp = _get_json(state["blueprint_ref"])
    key = _key(state, "schema.sql")
    get_storage().put(key, generate_ddl(bp).encode(), "application/sql")
    return {"ddl_ref": key}


@_stage(JobStatus.BACKEND_GENERATION)
def backend_generation(state: WorkflowState) -> dict:
    files = generate_backend(_get_json(state["blueprint_ref"]))
    return {"files_ref": _put_json(state, "files.json", files)}


@_stage(JobStatus.STATIC_CHECKS)
def static_checks(state: WorkflowState) -> dict:
    report = run_static_checks(_get_json(state["files_ref"]))
    ref = _put_json(state, "static_report.json", report)
    if not report["passed"]:
        raise PipelineFailure("Statische Prüfung fehlgeschlagen", {"findings": report["findings"][:20]})
    return {"static_report_ref": ref}


@_stage(JobStatus.SANDBOX_TEST)
def sandbox_test(state: WorkflowState) -> dict:
    if not settings.SANDBOX_ENABLED:
        return {"test_result_ref": _put_json(state, "test_result.json", {"status": "skipped"})}
    result = SandboxClient().run_tests(_get_json(state["files_ref"]))  # SandboxUnavailable -> retry
    ref = _put_json(state, "test_result.json", result)
    if result["status"] != "passed":
        raise PipelineFailure("Tests in der Sandbox fehlgeschlagen",
                              {"status": result["status"], "output": result["stdout"][-2000:]})
    return {"test_result_ref": ref}


@_stage(JobStatus.SECURITY_REVIEW)
def security_review(state: WorkflowState) -> dict:
    bp = _get_json(state["blueprint_ref"])
    report = run_security_review(_get_json(state["files_ref"]), [e["table"] for e in bp["entities"]])
    ref = _put_json(state, "security_report.json", report)
    if not report["passed"]:
        raise PipelineFailure("Sicherheitsprüfung hat blockierende Befunde",
                              {"findings": [f for f in report["findings"] if f["severity"] == "high"][:20]})
    return {"security_report_ref": ref, "summary": {**state.get("summary", {}),
                                                    "security_findings": len(report["findings"])}}


@_stage(JobStatus.HUMAN_RELEASE_APPROVAL)
def release_approval(state: WorkflowState) -> dict:
    decision = interrupt({"stage": "release", "summary": state.get("summary")})
    return {"decisions": [*state.get("decisions", []), {"stage": "release", **decision}]}


@_stage(JobStatus.PACKAGED)
def package(state: WorkflowState) -> dict:
    bp = _get_json(state["blueprint_ref"])
    files = dict(_get_json(state["files_ref"]))
    sec = _get_json(state["security_report_ref"])
    files["SECURITY_REPORT.json"] = json.dumps({"findings": sec["findings"]}, indent=2, sort_keys=True) + "\n"
    files["MANIFEST.json"] = manifest(files, {"app": bp["name"], "version": bp["version"],
                                              "generator": GENERATOR_VERSION, "workflow": WORKFLOW_VERSION})
    data, sha = build_zip(files, bp["name"])
    key = _key(state, f"{bp['name']}-{bp['version']}.zip")
    get_storage().put(key, data, "application/zip")
    return {"artifact_ref": key, "artifact_sha256": sha}


def complete(state: WorkflowState) -> dict:
    jobstore.set_status(state["tenant_id"], state["job_id"], JobStatus.COMPLETED,
                        {"artifact_sha256": state["artifact_sha256"]},
                        artifact_ref=state["artifact_ref"], artifact_sha256=state["artifact_sha256"],
                        result={"summary": state.get("summary"), "artifact_sha256": state["artifact_sha256"]},
                        error=None)
    return {"status": JobStatus.COMPLETED.value}


def rejected(state: WorkflowState) -> dict:
    last = (state.get("decisions") or [{}])[-1]
    jobstore.set_status(state["tenant_id"], state["job_id"], JobStatus.REJECTED,
                        {"stage": last.get("stage"), "by": last.get("actor"), "comment": last.get("comment")},
                        error=f"Abgelehnt bei {last.get('stage')}")
    return {"status": JobStatus.REJECTED.value}


def _approved(state: WorkflowState) -> str:
    last = (state.get("decisions") or [{}])[-1]
    return "yes" if last.get("approve") else "no"


def build_graph() -> StateGraph:
    g = StateGraph(WorkflowState)
    for fn in (validate_spec, blueprint_approval, ddl_generation, backend_generation, static_checks,
               sandbox_test, security_review, release_approval, package, complete, rejected):
        g.add_node(fn.__name__, fn)
    g.set_entry_point("validate_spec")
    g.add_edge("validate_spec", "blueprint_approval")
    g.add_conditional_edges("blueprint_approval", _approved, {"yes": "ddl_generation", "no": "rejected"})
    g.add_edge("ddl_generation", "backend_generation")
    g.add_edge("backend_generation", "static_checks")
    g.add_edge("static_checks", "sandbox_test")
    g.add_edge("sandbox_test", "security_review")
    g.add_edge("security_review", "release_approval")
    g.add_conditional_edges("release_approval", _approved, {"yes": "package", "no": "rejected"})
    g.add_edge("package", "complete")
    g.add_edge("complete", END)
    g.add_edge("rejected", END)
    return g


def initial_state(tenant_id: str, job_id: str, trace_id: str) -> WorkflowState:
    return {"tenant_id": tenant_id, "job_id": job_id, "trace_id": trace_id,
            "workflow_version": WORKFLOW_VERSION, "status": JobStatus.RECEIVED.value, "decisions": []}
