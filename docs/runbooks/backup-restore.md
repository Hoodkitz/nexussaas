# Backup & restore

- `scripts/backup.sh [dir]`: `pg_dump -Fc` of the database plus a tarball of local object storage,
  with SHA256SUMS; keeps the 14 newest sets. Run daily (cron/systemd timer). For S3 use bucket versioning.
- `scripts/restore.sh <dump> [target_db] [objects.tar.gz]`: restores into a scratch DB by default
  (`nexussaas_restore_check`) and prints tenant/job counts and the number of FORCE-RLS tables.
  Restoring over the live DB requires `FORCE=1` and stopped API/worker.
- Verified 10 Nov 2026: backup and restore round trip, counts identical, RLS intact.
- Monthly: run a restore into a scratch DB and compare counts (restore test).
- Backups enthalten personenbezogene Daten: Skript setzt umask 077 / chmod 700; für Offsite-Kopien verschlüsseln (z.B. age/gpg).
