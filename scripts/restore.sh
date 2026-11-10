#!/usr/bin/env bash
# Restore a backup into a target database (default: a scratch DB for verification).
# Usage: scripts/restore.sh <db-dump> [target_db] [objects-tar.gz]
#   Restoring into the live DB "nexussaas" requires FORCE=1 and stopped API/worker.
set -euo pipefail
cd "$(dirname "$0")/.."
DUMP="$1"; TARGET="${2:-nexussaas_restore_check}"; OBJ="${3:-}"
if [ "$TARGET" = "nexussaas" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "Refusing to overwrite the live database without FORCE=1" >&2; exit 1
fi
docker compose exec -T db psql -U nexussaas -d postgres -qc "DROP DATABASE IF EXISTS \"$TARGET\" WITH (FORCE)"
docker compose exec -T db psql -U nexussaas -d postgres -qc "CREATE DATABASE \"$TARGET\""
docker compose exec -T db pg_restore -U nexussaas -d "$TARGET" --no-owner --exit-on-error < "$DUMP"
docker compose exec -T db psql -U nexussaas -d "$TARGET" -qc "GRANT USAGE ON SCHEMA public TO nexus_app; GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO nexus_app; GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexus_app; REVOKE ALL ON alembic_version FROM nexus_app"
if [ -n "$OBJ" ]; then
  mkdir -p var && tar -C var -xzf "$OBJ"
fi
docker compose exec -T db psql -U nexussaas -d "$TARGET" -tAc \
  "SELECT 'tenants=' || count(*) FROM tenants UNION ALL SELECT 'jobs=' || count(*) FROM jobs UNION ALL SELECT 'rls_forced=' || count(*) FROM pg_class WHERE relforcerowsecurity"
