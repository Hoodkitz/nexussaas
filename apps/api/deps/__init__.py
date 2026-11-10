"""FastAPI dependencies: authentication, tenant context, RBAC."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from packages.domain.models import TenantMembership, User
from packages.security.rbac import has_permission
from packages.security.tokens import decode_access_token
from packages.storage.db import new_session

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    user: User
    tenant_id: Optional[uuid.UUID]
    role: Optional[str]
    db: Session

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    def can(self, permission: str) -> bool:
        return self.role is not None and has_permission(self.role, permission)


def _unauthorized(detail: str = "Nicht angemeldet") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def db_session() -> Iterator[Session]:
    """Session without tenant context (auth lookups, system tables)."""
    db = new_session()
    try:
        yield db
    finally:
        db.close()


def get_principal(request: Request,
                  creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Iterator[Principal]:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        claims = decode_access_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
        tenant_id = uuid.UUID(claims["tid"]) if claims.get("tid") else None
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Token ungültig oder abgelaufen")

    db = new_session(tenant_id, user_id)
    try:
        user = db.get(User, user_id)
        if user is None or not user.is_active or user.token_version != claims.get("ver"):
            raise _unauthorized("Token widerrufen")
        role = None
        if tenant_id is not None:
            m = (db.query(TenantMembership)
                 .filter(TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id)
                 .one_or_none())
            if m is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Kein Mitglied dieses Tenants")
            role = m.role
        request.state.user_id = str(user_id)
        request.state.tenant_id = str(tenant_id) if tenant_id else None
        yield Principal(user=user, tenant_id=tenant_id, role=role, db=db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def require(permission: str) -> Callable[..., Principal]:
    def dep(p: Principal = Depends(get_principal)) -> Principal:
        if p.tenant_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kein Tenant ausgewählt")
        if not p.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Fehlende Berechtigung: {permission}")
        return p
    return dep
