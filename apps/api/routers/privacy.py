"""DSGVO: Art. 15 data export and Art. 17 erasure (ADR-07: erasure is not a soft delete)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from apps.api.deps import Principal, get_principal
from packages.domain.models import AuditLog, Job, Subscription, Tenant, TenantMembership, User
from packages.security.audit import audit
from packages.storage.db import set_context
from packages.storage.object_storage import get_storage, tenant_prefix

router = APIRouter(prefix="/api/v1/users", tags=["privacy"])


class DeleteIn(BaseModel):
    confirm_email: EmailStr


def _memberships(p: Principal) -> list[TenantMembership]:
    set_context(p.db, None, p.user_id)
    return p.db.query(TenantMembership).filter(TenantMembership.user_id == p.user_id).all()


@router.get("/me/export")
def export_me(p: Principal = Depends(get_principal)):
    u = p.user
    out = {
        "user": {"id": str(u.id), "email": u.email, "name": u.name, "created_at": u.created_at,
                 "google_linked": bool(u.google_sub), "email_verified": u.email_verified},
        "memberships": [], "jobs": [], "audit": [],
    }
    for m in _memberships(p):
        set_context(p.db, m.tenant_id, p.user_id)
        t = p.db.get(Tenant, m.tenant_id)
        out["memberships"].append({"tenant_id": str(m.tenant_id), "tenant": t.name if t else None,
                                   "role": m.role, "since": m.created_at})
        for j in p.db.query(Job).filter(Job.tenant_id == m.tenant_id, Job.created_by == u.id):
            out["jobs"].append({"id": str(j.id), "tenant_id": str(j.tenant_id), "status": j.status,
                                "created_at": j.created_at, "blueprint": j.blueprint})
        for a in p.db.query(AuditLog).filter(AuditLog.tenant_id == m.tenant_id, AuditLog.actor_id == u.id):
            out["audit"].append({"tenant_id": str(a.tenant_id), "action": a.action, "target": a.target,
                                 "at": a.created_at})
    return out


@router.delete("/me", status_code=200)
def delete_me(req: DeleteIn, p: Principal = Depends(get_principal)):
    if req.confirm_email.lower() != p.user.email:
        raise HTTPException(400, "Bestätigungs-E-Mail stimmt nicht")
    ms = _memberships(p)
    to_delete, to_leave = [], []
    for m in ms:
        set_context(p.db, m.tenant_id, p.user_id)
        # Lock the tenant: membership changes take the same lock, so the counts below stay valid.
        p.db.get(Tenant, m.tenant_id, with_for_update=True)
        owners = p.db.query(TenantMembership).filter(TenantMembership.tenant_id == m.tenant_id,
                                                     TenantMembership.role == "owner").count()
        members = p.db.query(TenantMembership).filter(TenantMembership.tenant_id == m.tenant_id).count()
        if m.role == "owner" and owners == 1:
            if members > 1:
                raise HTTPException(409, f"Du bist einziger Owner von Tenant {m.tenant_id}. "
                                         "Übertrage zuerst die Owner-Rolle oder entferne die Mitglieder.")
            sub = p.db.get(Subscription, m.tenant_id)
            if sub and sub.status in ("active", "trialing", "past_due"):
                raise HTTPException(409, f"Tenant {m.tenant_id} hat ein aktives Abo. Bitte zuerst kündigen.")
            to_delete.append(m.tenant_id)
        else:
            to_leave.append(m.tenant_id)

    storage = get_storage()
    deleted_objects = 0
    for tid in to_delete:
        set_context(p.db, tid, p.user_id)
        job_ids = [str(j) for (j,) in p.db.query(Job.id).filter(Job.tenant_id == tid)]
        if job_ids:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                p.db.execute(text(f"DELETE FROM {table} WHERE thread_id = ANY(:ids)"), {"ids": job_ids})
        p.db.query(Tenant).filter(Tenant.id == tid).delete()  # cascades jobs, events, audit, subscription
        p.db.flush()
        deleted_objects += storage.delete_prefix(tenant_prefix(tid))
    for tid in to_leave:
        set_context(p.db, tid, p.user_id)
        audit(p.db, tid, None, "user.erased", None)  # no personal data in the record
        p.db.flush()
    set_context(p.db, None, p.user_id)
    p.db.query(User).filter(User.id == p.user_id).delete()  # memberships cascade, jobs.created_by -> NULL
    return {"status": "deleted", "tenants_deleted": len(to_delete), "tenants_left": len(to_leave),
            "objects_deleted": deleted_objects}
