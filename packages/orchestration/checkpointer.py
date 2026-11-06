"""LangGraph PostgreSQL checkpointer setup."""
import os

def get_checkpointer():
    """Create a PostgresSaver checkpointer for LangGraph."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
        db_url = os.getenv("DATABASE_URL", "postgresql+psycopg2://nexussaas:nexussaas@localhost:5432/nexussaas")
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
        # from_conn_string returns a context manager
        ctx = PostgresSaver.from_conn_string(db_url)
        checkpointer = ctx.__enter__()
        checkpointer.setup()
        return checkpointer
    except Exception as e:
        print(f"Checkpointer setup failed: {e}")
        return None

def build_graph_with_checkpointer():
    """Build LangGraph graph with PostgreSQL checkpointer."""
    from packages.orchestration.graph import build_graph
    graph = build_graph()
    if graph is None:
        return None
    checkpointer = get_checkpointer()
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()
