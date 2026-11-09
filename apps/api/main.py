"""NexusSaaS API entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import health, jobs, webhooks, auth, tenants, export, billing, oidc, blueprint

app = FastAPI(title="NexusSaaS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(jobs.router)
app.include_router(webhooks.router)
app.include_router(export.router)
app.include_router(billing.router)
app.include_router(oidc.router)
app.include_router(blueprint.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"service": "NexusSaaS", "version": "0.1.0"}
