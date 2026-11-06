"""Health and readiness endpoints."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/healthz")
def healthz():
    return {"status": "ok"}

@router.get("/readyz")
def readyz():
    checks = {"db": "unknown", "redis": "unknown"}
    try:
        import sqlalchemy
        from packages.storage.db import get_db
        # just check import availability
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "unavailable"
    try:
        from packages.storage.redis import get_redis
        r = get_redis()
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    status = "ready" if all(v == "ok" for v in checks.values()) else "not_ready"
    return {"status": status, **checks}
