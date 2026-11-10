"""LangGraph state. Holds only ids, object-storage keys and small summaries (ADR-03)."""
from typing import Optional, TypedDict


class WorkflowState(TypedDict, total=False):
    tenant_id: str
    job_id: str
    trace_id: str
    workflow_version: str
    status: str
    summary: dict
    blueprint_ref: Optional[str]
    ddl_ref: Optional[str]
    files_ref: Optional[str]
    static_report_ref: Optional[str]
    test_result_ref: Optional[str]
    security_report_ref: Optional[str]
    artifact_ref: Optional[str]
    artifact_sha256: Optional[str]
    decisions: list
