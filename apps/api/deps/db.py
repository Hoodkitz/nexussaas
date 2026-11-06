"""DB dependency for FastAPI."""
from packages.storage.db import get_db

# Re-export for convenience
__all__ = ["get_db"]
