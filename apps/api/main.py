"""NexusSaaS API entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware import RequestContextMiddleware
from apps.api.routers import auth, billing, blueprint, health, jobs, privacy, tenants
from packages.observability.logging import setup_logging
from packages.settings import settings

VERSION = "0.2.0"
setup_logging(settings.LOG_LEVEL)

app = FastAPI(title="NexusSaaS API", version=VERSION,
              docs_url=None if settings.ENV == "production" else "/docs")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials="*" not in settings.CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)

for r in (health, auth, tenants, jobs, billing, privacy):
    app.include_router(r.router)
app.include_router(blueprint.router, prefix="/api/v1")



@app.get("/")
def root():
    return {"service": "NexusSaaS", "version": VERSION}
