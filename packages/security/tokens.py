"""JWT access tokens (HS256). Role is NOT trusted from the token; it is re-read from the DB."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from packages.settings import settings

ALGORITHM = "HS256"
ISSUER = "nexussaas"


def create_access_token(user_id: str, tenant_id: Optional[str], token_version: int,
                        minutes: Optional[int] = None) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "iss": ISSUER,
        "sub": str(user_id),
        "tid": str(tenant_id) if tenant_id else None,
        "ver": token_version,
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes or settings.ACCESS_TOKEN_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM], issuer=ISSUER,
                        options={"require": ["exp", "sub", "iss"]})
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return claims
