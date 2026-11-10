"""Health, readiness and metrics endpoints."""
from fastapi import APIRouter, Response
from sqlalchemy import text

from packages.observability.metrics import render
from packages.storage.db import engine
from packages.storage.object_storage import get_storage
from packages.storage.redis import get_redis

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/readyz")
def readyz(response: Response):
    checks = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "unavailable"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    try:
        checks["storage"] = "ok" if get_storage().healthy() else "unavailable"
    except Exception:
        checks["storage"] = "unavailable"
    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ready" if ready else "not_ready", **checks}


@router.get("/metrics")
def metrics():
    body, ctype = render()
    return Response(body, media_type=ctype)
