"""Authentication: email/password (Argon2id) and Google OIDC (Authorization Code + PKCE).

No OAuth2 password grant is exposed (RFC 9700); /login is a first-party form endpoint.
"""
from __future__ import annotations

import html
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.deps import Principal, db_session, get_principal
from apps.api.schemas.models import LoginIn, MeOut, RegisterIn, SwitchTenantIn, TokenOut, UserOut
from packages.domain.models import Tenant, TenantMembership, User
from packages.domain.tenancy import create_tenant
from packages.mail import Mail, get_mailer
from packages.observability.metrics import AUTH_EVENTS
from packages.security import oidc
from packages.security.password import hash_password, validate_password_strength, verify_password
from packages.security.tokens import create_reset_token, decode_reset_token, create_access_token, create_email_token, decode_email_token
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


def send_verification_mail(user: User) -> None:
    token = create_email_token(str(user.id), user.email)
    link = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/auth/verify-email?token={token}"
    get_mailer().send(Mail(
        to=user.email, subject="NexusSaaS: E-Mail-Adresse bestätigen",
        # No user-supplied text (name) in mail to an unverified address: it could carry phishing content.
        text=("Hallo,\n\nbitte bestätige deine E-Mail-Adresse für NexusSaaS über diesen Link "
              f"(gültig {settings.EMAIL_VERIFY_HOURS} Stunden):\n\n{link}\n\nFalls du dich nicht registriert hast, "
              "ignoriere diese Nachricht.\n")))


def _discard_unverified_account(db: Session, user: User) -> None:
    for m in _memberships(db, user.id):
        set_context(db, m.tenant_id, user.id)
        others = db.query(TenantMembership).filter(TenantMembership.tenant_id == m.tenant_id,
                                                   TenantMembership.user_id != user.id).count()
        if others == 0:
            db.query(Tenant).filter(Tenant.id == m.tenant_id).delete()
    set_context(db, None, user.id)
    db.query(User).filter(User.id == user.id).delete()  # remaining memberships cascade
    db.flush()
    AUTH_EVENTS.labels("unverified_account_discarded").inc()


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
    try:
        send_verification_mail(user)
    except Exception:  # mail problems must not block registration; the user can resend
        AUTH_EVENTS.labels("verify_mail_failed").inc()
    return _token(user, tenant.id, "owner")


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=2048)


def _verify(token: str, db: Session) -> dict:
    try:
        claims = decode_email_token(token)
    except jwt.PyJWTError:
        raise HTTPException(400, "Bestätigungslink ungültig oder abgelaufen")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.email != claims["email"]:
        raise HTTPException(400, "Bestätigungslink passt nicht zum Konto")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
        AUTH_EVENTS.labels("email_verified").inc()
    return {"status": "verified", "email": user.email}


def _page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    """Minimal page for links opened from e-mails (phone browser). Only static text plus escaped values."""
    return HTMLResponse(status_code=status_code, content=f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;background:#000;color:#0f0;max-width:440px;margin:40px auto;padding:0 16px}}
input,button{{width:100%;padding:12px;margin:8px 0;font:inherit;background:#020;color:#0f0;border:1px solid #0a0;border-radius:6px}}
button{{background:#0a0;color:#000;font-weight:700}}</style></head><body><h1>{html.escape(title)}</h1>{body}</body></html>""")


@router.get("/verify-email")
def verify_email_link(token: str, db: Session = Depends(db_session)):
    """Target of the link in the mail."""
    try:
        r = _verify(token, db)
    except HTTPException as e:
        return _page("Bestätigung fehlgeschlagen", f"<p>{html.escape(str(e.detail))}</p>", e.status_code)
    return _page("E-Mail bestätigt", f"<p>{html.escape(r['email'])} ist bestätigt. Du kannst jetzt zurück in die App.</p>")


@router.post("/verify-email")
def verify_email(req: VerifyEmailIn, db: Session = Depends(db_session)):
    return _verify(req.token, db)


_last_resend: dict[str, float] = {}
_last_reset: dict[str, float] = {}


class ResetRequestIn(BaseModel):
    email: EmailStr


@router.post("/password-reset", status_code=202)
def request_password_reset(req: ResetRequestIn, db: Session = Depends(db_session)):
    """Always 202 (no account enumeration). Sends a one-hour, single-use link if the account exists."""
    import time
    email = req.email.lower()
    now = time.monotonic()
    if now - _last_reset.get(email, -1e9) < 60:
        return {"status": "sent"}
    _last_reset[email] = now
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None and user.is_active:
        token = create_reset_token(str(user.id), user.token_version or 0, user.hashed_password)
        link = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/api/v1/auth/password-reset/confirm?token={token}"
        try:
            get_mailer().send(Mail(to=user.email, subject="NexusSaaS: Passwort zurücksetzen", text=(
                "Hallo,\n\nüber diesen Link kannst du ein neues Passwort für NexusSaaS festlegen (gültig 1 Stunde, "
                f"nur einmal verwendbar):\n\n{link}\n\nFalls du das nicht angefordert hast, ignoriere diese Nachricht – "
                "dein Passwort bleibt unverändert.\n")))
        except Exception:
            AUTH_EVENTS.labels("reset_mail_failed").inc()
    return {"status": "sent"}


def _reset_user(token: str, db: Session) -> User:
    try:
        sub = jwt.decode(token, options={"verify_signature": False}).get("sub")
        user = db.get(User, uuid.UUID(str(sub)))
        if user is None:
            raise ValueError
        decode_reset_token(token, user.token_version or 0, user.hashed_password)
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(400, "Link ungültig, abgelaufen oder bereits verwendet")
    return user


@router.get("/password-reset/confirm")
def password_reset_form(token: str, db: Session = Depends(db_session)):
    try:
        _reset_user(token, db)
    except HTTPException as e:
        return _page("Passwort zurücksetzen", f"<p>{html.escape(str(e.detail))}</p>", e.status_code)
    return _page("Neues Passwort", f"""<form method="post" action="/api/v1/auth/password-reset/confirm">
<input type="hidden" name="token" value="{html.escape(token)}">
<input type="password" name="password" placeholder="Neues Passwort" minlength="10" required autocomplete="new-password">
<input type="password" name="password2" placeholder="Wiederholen" minlength="10" required autocomplete="new-password">
<button type="submit">Speichern</button></form>
<p>Mindestens 10 Zeichen mit Groß-/Kleinbuchstaben und Ziffer.</p>""")


@router.post("/password-reset/confirm")
async def password_reset_confirm(request: Request, db: Session = Depends(db_session)):
    from urllib.parse import parse_qs
    form = {k: v[0] for k, v in parse_qs((await request.body())[:10_000].decode(errors="replace")).items()}
    try:
        user = _reset_user(form.get("token", ""), db)
    except HTTPException as e:
        return _page("Passwort zurücksetzen", f"<p>{html.escape(str(e.detail))}</p>", e.status_code)
    pw = form.get("password", "")
    if pw != form.get("password2", ""):
        return _page("Neues Passwort", "<p>Die Passwörter stimmen nicht überein. Bitte den Link erneut öffnen.</p>", 422)
    problems = validate_password_strength(pw)
    if problems:
        return _page("Neues Passwort", "<p>" + html.escape(" ".join(problems)) + " Bitte den Link erneut öffnen.</p>", 422)
    if not user.is_active:
        return _page("Passwort zurücksetzen", "<p>Dieses Konto ist deaktiviert.</p>", 403)
    if not user.email_verified:
        # Mailbox proven only now: content of the unproven account may be a squatter's. Start fresh, like Google.
        email, name = user.email, None
        _discard_unverified_account(db, user)
        user = User(id=uuid.uuid4(), email=email, name=name, hashed_password=hash_password(pw), email_verified=True)
        db.add(user)
        db.flush()
        create_tenant(db, user.id, f"{email.split('@')[0]}s Workspace")
    else:
        user.hashed_password = hash_password(pw)
        user.token_version = (user.token_version or 0) + 1  # every existing session ends
    db.commit()
    AUTH_EVENTS.labels("password_reset").inc()
    return _page("Passwort geändert", "<p>Dein neues Passwort ist gespeichert. Melde dich jetzt in der App an.</p>")


@router.post("/resend-verification", status_code=202)
def resend_verification(p: Principal = Depends(get_principal)):
    if p.user.email_verified:
        return {"status": "already_verified"}
    import time
    now = time.monotonic()
    if now - _last_resend.get(str(p.user_id), -1e9) < 60:  # protects the mail quota and the recipient
        raise HTTPException(429, "Bitte eine Minute warten, bevor die Mail erneut gesendet wird")
    _last_resend[str(p.user_id)] = now
    send_verification_mail(p.user)
    return {"status": "sent"}


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
            if not user.is_active:
                raise HTTPException(403, "Konto deaktiviert")
            if not user.email_verified:
                # The address was never proven by that password account, but Google just proved it for this
                # person. Nothing of the unproven account may carry over (it could be a squatter's, with planted
                # members or data): delete it and its sole-member workspaces, then sign up the real owner fresh.
                _discard_unverified_account(db, user)
                user = None
            else:
                user.google_sub = info["sub"]
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
