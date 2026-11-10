# Deploy runbook

## Prerequisites
- PostgreSQL 16, Redis 7, S3-compatible object storage (or local dir in dev)
- Docker on the worker host and the sandbox image (`make sandbox-image`)
- `.env` with `ENV=production`, a 32+ char `SECRET_KEY`, real DB passwords, `CORS_ORIGINS`

## Steps
1. `make migrate` (runs as owner role, creates/updates `nexus_app` and RLS policies)
2. Start API: `uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers`
   behind a TLS reverse proxy. Restrict `/metrics` and `/docs` at the proxy.
3. Start one or more workers: `python -m apps.worker.main` (SIGTERM for graceful stop)
4. Optional: `make install-services` installs systemd user units for both.
5. Verify: `curl /readyz` returns `ready` (db, redis, storage).

## Rollback
1. Stop workers (in-flight jobs resume from checkpoints after restart).
2. Redeploy previous release; `alembic downgrade -1` only if the release added a migration.
3. Restore from backup if data was damaged: see `backup-restore.md`.
