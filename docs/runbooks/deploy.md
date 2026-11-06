# Deploy Runbook

## Prerequisites
- PostgreSQL 16+ running
- Redis 7+ running
- Object storage (S3-compatible) configured
- Environment variables set (DATABASE_URL, REDIS_URL, SECRET_KEY)

## Steps
1. Run migrations: `alembic upgrade head`
2. Start API: `uvicorn apps.api.main:app --host 0.0.0.0 --port 8000`
3. Start worker: `python -m apps.worker.main`
4. Verify: `curl http://localhost:8000/healthz`

## Rollback
1. `alembic downgrade -1`
2. Restart API + worker
