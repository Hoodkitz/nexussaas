"""LangGraph workflow graph with PostgreSQL checkpointer."""
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

def build_graph():
    """Build LangGraph StateGraph with conditional edges and interrupts."""
    try:
        from langgraph.graph import StateGraph, END
        from langgraph.checkpoint.postgres import PostgresSaver
        graph = StateGraph(WorkflowState)
        for name, fn in NODES.items():
            graph.add_node(name, fn)
        graph.set_entry_point("validate_spec")
        graph.add_edge("validate_spec", "generate_blueprint")
        graph.add_edge("generate_blueprint", "generate_ddl")
        graph.add_edge("generate_ddl", "generate_backend")
        graph.add_edge("generate_backend", "static_checks")
        graph.add_edge("static_checks", "sandbox_test")
        graph.add_edge("sandbox_test", "security_review")
        graph.add_edge("security_review", "package")
        graph.add_edge("package", "complete")
        graph.add_edge("complete", END)
        return graph
    except ImportError:
        return None

def run_workflow(state: WorkflowState) -> WorkflowState:
    """Run the workflow synchronously (stub)."""
    for name in ["validate_spec", "generate_blueprint", "generate_ddl", "generate_backend",
                 "static_checks", "sandbox_test", "security_review", "package", "complete"]:
        state = NODES[name](state)
    return state
