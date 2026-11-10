# Data deletion (DSGVO Art. 17) and export (Art. 15)

ADR-07: erasure is a hard delete, never a soft delete flag.

- Export: `GET /api/v1/users/me/export` returns profile, memberships, the user's jobs (with blueprints)
  and audit entries performed by the user.
- Erasure: `DELETE /api/v1/users/me` with `{"confirm_email": "<own email>"}`
  - Tenants where the user is the only member and owner are deleted entirely: jobs, events, audit log,
    subscription, LangGraph checkpoints and all objects under `tenants/<id>/`.
  - Sole owner of a tenant with other members: refused (409) until ownership is transferred.
  - Active subscription: refused (409) until it is cancelled in Stripe.
  - Shared tenants: membership removed, `jobs.created_by` set to NULL, an anonymous `user.erased`
    audit record is written. The users row is deleted.
- Backups: erased data disappears from backups after the 14-day backup rotation. Document requests
  in the processing register; do not restore erased users from backup.
