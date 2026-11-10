#!/usr/bin/env bash
# Consistent PostgreSQL backup (custom format) + object storage snapshot.
# Usage: scripts/backup.sh [backup_dir]   (default: var/backups)
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${1:-var/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DIR"
docker compose exec -T db pg_dump -U nexussaas -d nexussaas -Fc --no-owner > "$DIR/db-$STAMP.dump"
if [ -d var/objects ]; then
  tar -C var -czf "$DIR/objects-$STAMP.tar.gz" objects
fi
sha256sum "$DIR"/*-"$STAMP".* > "$DIR/SHA256SUMS-$STAMP"
# keep the newest 14 sets
ls -1t "$DIR"/db-*.dump 2>/dev/null | tail -n +15 | while read -r f; do
  s="${f##*/db-}"; s="${s%.dump}"; rm -f "$DIR"/*-"$s".* "$DIR/SHA256SUMS-$s"
done
echo "$DIR/db-$STAMP.dump"
