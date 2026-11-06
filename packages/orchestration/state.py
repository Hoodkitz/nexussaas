"""LangGraph state definition."""
from typing import TypedDict, Optional, Annotated
import operator

class WorkflowState(TypedDict):
    tenant_id: str
    job_id: str
    workflow_version: str
    blueprint: Optional[dict]
    blueprint_ref: Optional[str]
    generated_artifact_ref: Optional[str]
    test_result_ref: Optional[str]
    security_findings: Optional[list]
    status: str
    attempt: int
    budget_usage: dict
    trace_id: str
    messages: Annotated[list, operator.add]
