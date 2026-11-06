"""LangGraph workflow graph (stub)."""
from packages.orchestration.state import WorkflowState

def validate_spec(state: WorkflowState) -> WorkflowState:
    state["status"] = "SPEC_VALIDATION"
    return state

def generate_blueprint(state: WorkflowState) -> WorkflowState:
    state["status"] = "BLUEPRINT_APPROVAL"
    return state

def generate_ddl(state: WorkflowState) -> WorkflowState:
    state["status"] = "DDL_GENERATION"
    return state

def generate_backend(state: WorkflowState) -> WorkflowState:
    state["status"] = "BACKEND_GENERATION"
    return state

def static_checks(state: WorkflowState) -> WorkflowState:
    state["status"] = "STATIC_CHECKS"
    return state

def sandbox_test(state: WorkflowState) -> WorkflowState:
    state["status"] = "SANDBOX_TEST"
    return state

def security_review(state: WorkflowState) -> WorkflowState:
    state["status"] = "SECURITY_REVIEW"
    return state

def package(state: WorkflowState) -> WorkflowState:
    state["status"] = "PACKAGED"
    return state

def complete(state: WorkflowState) -> WorkflowState:
    state["status"] = "COMPLETED"
    return state

# Graph definition (to be wired with LangGraph StateGraph when langgraph is installed)
NODES = {
    "validate_spec": validate_spec,
    "generate_blueprint": generate_blueprint,
    "generate_ddl": generate_ddl,
    "generate_backend": generate_backend,
    "static_checks": static_checks,
    "sandbox_test": sandbox_test,
    "security_review": security_review,
    "package": package,
    "complete": complete,
}

def run_workflow(state: WorkflowState) -> WorkflowState:
    """Run the workflow synchronously (stub)."""
    for name in ["validate_spec", "generate_blueprint", "generate_ddl", "generate_backend",
                 "static_checks", "sandbox_test", "security_review", "package", "complete"]:
        state = NODES[name](state)
    return state
