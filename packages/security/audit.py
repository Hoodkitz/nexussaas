"""Append-only audit log helper (tenant-scoped)."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from packages.domain.models import AuditLog


def audit(db: Session, tenant_id, actor_id, action: str, target: Optional[str] = None,
          detail: Optional[dict[str, Any]] = None) -> None:
    db.add(AuditLog(tenant_id=tenant_id, actor_id=actor_id, action=action, target=target, detail=detail))
