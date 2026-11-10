"""Tenant creation and slug helpers."""
from __future__ import annotations

import re
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from packages.domain.models import Subscription, Tenant, TenantMembership, UserRole
from packages.security.audit import audit
from packages.settings import settings
from packages.storage.db import set_context

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.lower()).strip("-")[:60]
    return s or "tenant"


def create_tenant(db: Session, owner_id: uuid.UUID, name: str, slug: str | None = None) -> Tenant:
    """Create a tenant with the given owner. Switches the session context to the new tenant."""
    tenant_id = uuid.uuid4()
    set_context(db, tenant_id, owner_id)
    # Other tenants' slugs are invisible under RLS, so uniqueness is ensured by a random
    # suffix plus the DB unique constraint (retried inside a savepoint).
    base = slugify(slug or name)
    for _ in range(5):
        final = f"{base}-{secrets.token_hex(3)}"
        try:
            with db.begin_nested():
                tenant = Tenant(id=tenant_id, name=name.strip(), slug=final,
                                status="pilot" if settings.PILOT_MODE else "active")
                db.add(tenant)
                db.flush()
            break
        except IntegrityError:
            continue
    else:  # pragma: no cover
        raise RuntimeError("could not allocate tenant slug")
    db.add(TenantMembership(tenant_id=tenant_id, user_id=owner_id, role=UserRole.OWNER.value))
    db.add(Subscription(tenant_id=tenant_id, status="none", plan="free"))
    audit(db, tenant_id, owner_id, "tenant.created", str(tenant_id), {"slug": final})
    db.flush()
    return tenant
