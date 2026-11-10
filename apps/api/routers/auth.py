"""Authentication: email/password (Argon2id) and Google OIDC (Authorization Code + PKCE).

No OAuth2 password grant is exposed (RFC 9700); /login is a first-party form endpoint.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.deps import Principal, db_session, get_principal
from apps.api.schemas.models import LoginIn, MeOut, RegisterIn, SwitchTenantIn, TokenOut, UserOut
from packages.domain.models import Tenant, TenantMembership, User
from packages.domain.tenancy import create_tenant
from packages.observability.metrics import AUTH_EVENTS
from packages.security import oidc
from packages.security.audit import audit
from packages.security.password import hash_password, validate_password_strength, verify_password
from packages.security.tokens import create_access_token
from packages.settings import settings
from packages.storage.db import set_context

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _token(user: User, tenant_id, role) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(str(user.id), str(tenant_id) if tenant_id else None, user.token_version),
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        tenant_id=str(tenant_id) if tenant_id else None,
        role=role,
    )


def _pilot_check(email: str) -> None:
    if settings.PILOT_MODE and email.lower() not in settings.PILOT_ALLOWED_EMAILS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registrierung ist im Pilotbetrieb nur auf Einladung möglich")


def _memberships(db: Session, user_id) -> list[TenantMembership]:
    set_context(db, None, user_id)
    return (db.query(TenantMembership).filter(TenantMembership.user_id == user_id)
            .order_by(TenantMembership.created_at).all())


@router.post("/register", response_model=TokenOut, status_code=201)
def register(req: RegisterIn, db: Session = Depends(db_session)):
    email = req.email.lower()
    _pilot_check(email)
    problems = validate_password_strength(req.password)
    if problems:
        raise HTTPException(422, detail=problems)
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert")
    user = User(id=uuid.uuid4(), email=email, name=req.name, hashed_password=hash_password(req.password))
    db.add(user)
    try:
        db.flush()
        tenant = create_tenant(db, user.id, req.tenant_name or f"{req.name or email.split('@')[0]}s Workspace")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail ist bereits registriert")
    AUTH_EVENTS.labels("register").inc()
    return _token(user, tenant.id, "owner")


@router.post("/login", response_model=TokenOut)
def login(req: LoginIn, db: Session = Depends(db_session)):
    user = db.query(User).filter(User.email == req.email.lower()).one_or_none()
    ok = verify_password(req.password, user.hashed_password if user else None)
    if not user or not ok or not user.is_active:
        AUTH_EVENTS.labels("login_failed").inc()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch")
    ms = _memberships(db, user.id)
    chosen = ms[0] if ms else None
    if req.tenant_id:
        chosen = next((m for m in ms if str(m.tenant_id) == req.tenant_id), None)
        if chosen is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Kein Mitglied dieses Tenants")
    AUTH_EVENTS.labels("login").inc()
    return _token(user, chosen.tenant_id if chosen else None, chosen.role if chosen else None)


@router.get("/me", response_model=MeOut)
def me(p: Principal = Depends(get_principal)):
    ms = _memberships(p.db, p.user_id)
    tenants = []
    for m in ms:
        set_context(p.db, m.tenant_id, p.user_id)
        t = p.db.get(Tenant, m.tenant_id)
        tenants.append({"id": str(m.tenant_id), "name": t.name if t else None, "role": m.role})
    return MeOut(user=UserOut(id=str(p.user.id), email=p.user.email, name=p.user.name),
                 tenant_id=str(p.tenant_id) if p.tenant_id else None, role=p.role, tenants=tenants)


@router.post("/switch-tenant", response_model=TokenOut)
def switch_tenant(req: SwitchTenantIn, p: Principal = Depends(get_principal)):
    m = next((m for m in _memberships(p.db, p.user_id) if str(m.tenant_id) == req.tenant_id), None)
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Kein Mitglied dieses Tenants")
    return _token(p.user, m.tenant_id, m.role)


@router.post("/logout-all", status_code=204)
def logout_all(p: Principal = Depends(get_principal)):
    """Revoke all tokens of the current user."""
    p.user.token_version += 1


def _reset_unverified_access(db: Session, user_id) -> None:
    """Undo everything that may have been set up while the address was unverified:
    other members in tenants this user owns are removed, and memberships in tenants
    the user does not own are dropped."""
    for m in _memberships(db, user_id):
        set_context(db, m.tenant_id, user_id)
        if m.role == "owner":
            others = (db.query(TenantMembership)
                      .filter(TenantMembership.tenant_id == m.tenant_id, TenantMembership.user_id != user_id).all())
            for o in others:
                db.delete(o)
            audit(db, m.tenant_id, user_id, "auth.unverified_link_reset", str(user_id),
                  {"removed_members": [str(o.user_id) for o in others]})
        else:
            db.delete(m)
    db.flush()
    set_context(db, None, user_id)


@router.get("/google")
def google_login():
    if not oidc.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Google-Login ist nicht konfiguriert")
    return {"authorization_url": oidc.start_login()}


@router.get("/google/callback", response_model=TokenOut)
async def google_callback(code: str, state: str, db: Session = Depends(db_session)):
    st = oidc.consume_state(state)
    if not st:
        raise HTTPException(400, "Ungültiger oder abgelaufener state")
    try:
        tokens = await oidc.exchange_code(code, st["verifier"])
        info = await oidc.fetch_userinfo(tokens["access_token"])
    except Exception:
        raise HTTPException(400, "Google-Anmeldung fehlgeschlagen")
    if not info.get("email") or not info.get("email_verified"):
        raise HTTPException(400, "Google-Konto ohne bestätigte E-Mail")
    email = info["email"].lower()
    user = db.query(User).filter(User.google_sub == info["sub"]).one_or_none()
    if user is None:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is not None:
            # Google proved ownership of the address. If the existing account was never
            # verified, someone else may have pre-registered it: drop its password and
            # revoke all sessions so only the verified owner keeps access.
            if not user.email_verified:
                user.hashed_password = None
                user.token_version += 1
                _reset_unverified_access(db, user.id)
            user.google_sub = info["sub"]
            user.email_verified = True
    if user is None:
        _pilot_check(email)
        user = User(id=uuid.uuid4(), email=email, name=info.get("name"), google_sub=info["sub"],
                    email_verified=True)
        db.add(user)
        db.flush()
        create_tenant(db, user.id, f"{info.get('name') or email.split('@')[0]}s Workspace")
    if not user.is_active:
        raise HTTPException(403, "Konto deaktiviert")
    db.commit()
    ms = _memberships(db, user.id)
    m = ms[0] if ms else None
    return _token(user, m.tenant_id if m else None, m.role if m else None)
