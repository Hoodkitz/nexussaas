# Data Deletion Runbook (Art. 17 DSGVO)

## Trigger
User requests deletion via DELETE /api/v1/users/me

## Steps
1. Soft-delete user (status = "deleted", timestamp)
2. Create deletion job in outbox
3. Worker processes:
   a. Delete active DB records (tenant-scoped)
   b. Delete object storage artifacts
   c. Purge from cache/Redis
   d. Remove from search index
   e. Anonymize logs (replace PII with hash)
   f. Record in deletion registry
4. Backups: mark for crypto-shredding / beyond-use
5. Confirm to user within 30 days

## Retention Exceptions
- Legal hold (audit logs, billing records)
- Statutory retention periods
- Document reason and scope
