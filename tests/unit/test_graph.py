"""Workflow graph tests."""
from packages.orchestration.state import WorkflowState
from packages.orchestration.graph import run_workflow

def test_workflow_completes():
    state: WorkflowState = {
        "tenant_id": "t1", "job_id": "j1", "workflow_version": "1.0",
        "blueprint": None, "blueprint_ref": None, "generated_artifact_ref": None,
        "test_result_ref": None, "security_findings": None, "status": "RECEIVED",
        "attempt": 0, "budget_usage": {}, "trace_id": "abc", "messages": [],
    }
    result = run_workflow(state)
    assert result["status"] == "COMPLETED"
    assert result["attempt"] == 0
