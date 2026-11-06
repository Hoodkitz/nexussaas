"""NexusSaaS API entry point."""
from fastapi import FastAPI

app = FastAPI(title="NexusSaaS API", version="0.1.0")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz():
    return {"status": "ready"}
