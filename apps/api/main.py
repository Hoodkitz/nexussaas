"""NexusSaaS API entry point."""
from fastapi import FastAPI
from apps.api.routers import health, jobs, webhooks, auth, tenants, export, billing

app = FastAPI(title="NexusSaaS API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(jobs.router)
app.include_router(webhooks.router)
app.include_router(export.router)
app.include_router(billing.router)

@app.get("/")
def root():
    return {"service": "NexusSaaS", "version": "0.1.0"}
