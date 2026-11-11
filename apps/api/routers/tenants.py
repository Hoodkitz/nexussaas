"""Tenants and memberships."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from apps.api.deps import Principal, get_principal, require
from apps.api.schemas.models import MemberIn, MemberOut, MemberRoleIn, TenantCreate, TenantOut, TokenOut
from packages.domain.models import Tenant, TenantMembership, User
from packages.domain.tenancy import create_tenant
from packages.security.audit import audit
from packages.security.rbac import ROLE_RANK
from packages.security.tokens import create_access_token
from packages.settings import settings

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


def _out(t: Tenant) -> TenantOut:
    return TenantOut(id=str(t.id), name=t.name, slug=t.slug, plan=t.plan, status=t.status, created_at=t.created_at)


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, "Nicht gefunden")


@router.post("", response_model=TokenOut, status_code=201)
def create(req: TenantCreate, p: Principal = Depends(get_principal)):
    """Create a tenant; the caller becomes owner. Returns a token scoped to the new tenant."""
    owned = p.db.query(TenantMembership).filter(TenantMembership.user_id == p.user_id,
                                                TenantMembership.role == "owner").count()
    if owned >= settings.MAX_OWNED_TENANTS:  # quotas are per tenant: unlimited tenants would bypass them
        raise HTTPException(409, f"Höchstens {settings.MAX_OWNED_TENANTS} eigene Workspaces pro Konto")
    t = create_tenant(p.db, p.user_id, req.name, req.slug)
    return TokenOut(access_token=create_access_token(str(p.user_id), str(t.id), p.user.token_version),
                    expires_in=settings.ACCESS_TOKEN_MINUTES * 60, tenant_id=str(t.id), role="owner")


@router.get("/current", response_model=TenantOut)
def current(p: Principal = Depends(require("read"))):
    return _out(p.db.get(Tenant, p.tenant_id))


@router.get("/{tenant_id}", response_model=TenantOut)
def get(tenant_id: str, p: Principal = Depends(get_principal)):
    # RLS only returns tenants the user belongs to.
    t = p.db.get(Tenant, _uuid(tenant_id))
    if t is None:
        raise HTTPException(404, "Nicht gefunden")
    return _out(t)


@router.get("/current/members", response_model=list[MemberOut])
def members(p: Principal = Depends(require("read"))):
    rows = (p.db.query(TenantMembership, User).join(User, User.id == TenantMembership.user_id)
            .filter(TenantMembership.tenant_id == p.tenant_id).order_by(TenantMembership.created_at).all())
    return [MemberOut(user_id=str(u.id), email=u.email, name=u.name, role=m.role) for m, u in rows]


@router.post("/current/members", response_model=MemberOut, status_code=201)
def add_member(req: MemberIn, p: Principal = Depends(require("admin"))):
    _lock_tenant(p)
    user = p.db.query(User).filter(User.email == req.email.lower(), User.is_active.is_(True)).one_or_none()
    if user is None:
        raise HTTPException(404, "Kein Konto mit dieser E-Mail; die Person muss sich zuerst registrieren")
    exists = p.db.query(TenantMembership).filter(TenantMembership.tenant_id == p.tenant_id,
                                                 TenantMembership.user_id == user.id).one_or_none()
    if exists:
        raise HTTPException(409, "Bereits Mitglied")
    p.db.add(TenantMembership(tenant_id=p.tenant_id, user_id=user.id, role=req.role))
    audit(p.db, p.tenant_id, p.user_id, "member.added", str(user.id), {"role": req.role})
    return MemberOut(user_id=str(user.id), email=user.email, name=user.name, role=req.role)


def _membership(p: Principal, user_id: str) -> TenantMembership:
    m = p.db.query(TenantMembership).filter(TenantMembership.tenant_id == p.tenant_id,
                                            TenantMembership.user_id == _uuid(user_id)).one_or_none()
    if m is None:
        raise HTTPException(404, "Mitglied nicht gefunden")
    return m


def _lock_tenant(p: Principal) -> None:
    """Serialize membership changes per tenant (owner invariants, account erasure)."""
    p.db.get(Tenant, p.tenant_id, with_for_update=True)


def _owners(p: Principal) -> int:
    return p.db.query(TenantMembership).filter(TenantMembership.tenant_id == p.tenant_id,
                                               TenantMembership.role == "owner").count()


@router.patch("/current/members/{user_id}", response_model=MemberOut)
def change_role(user_id: str, req: MemberRoleIn, p: Principal = Depends(require("admin"))):
    _lock_tenant(p)
    m = _membership(p, user_id)
    # Only owners may grant or revoke owner; admins cannot touch owners.
    if (req.role == "owner" or m.role == "owner") and p.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur Owner dürfen Owner-Rechte ändern")
    if m.role == "owner" and req.role != "owner" and _owners(p) <= 1:
        raise HTTPException(409, "Der letzte Owner kann nicht herabgestuft werden")
    old, m.role = m.role, req.role
    audit(p.db, p.tenant_id, p.user_id, "member.role_changed", user_id, {"from": old, "to": req.role})
    u = p.db.get(User, m.user_id)
    return MemberOut(user_id=str(u.id), email=u.email, name=u.name, role=m.role)


@router.delete("/current/members/{user_id}", status_code=204)
def remove_member(user_id: str, p: Principal = Depends(require("read"))):
    _lock_tenant(p)
    m = _membership(p, user_id)
    is_self = m.user_id == p.user_id
    if not is_self:
        if not p.can("admin") or ROLE_RANK[m.role] > ROLE_RANK[p.role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung")
    if m.role == "owner" and _owners(p) <= 1:
        raise HTTPException(409, "Der letzte Owner kann nicht entfernt werden")
    p.db.delete(m)
    audit(p.db, p.tenant_id, p.user_id, "member.removed", user_id)
