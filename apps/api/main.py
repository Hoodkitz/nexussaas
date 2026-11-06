"""NexusSaaS API entry point."""
from fastapi import FastAPI
from apps.api.routers import health, jobs, webhooks

app = FastAPI(title="NexusSaaS API", version="0.1.0")

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(webhooks.router)

@app.get("/")
def root():
    return {"service": "NexusSaaS", "version": "0.1.0"}
