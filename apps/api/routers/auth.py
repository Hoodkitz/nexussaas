"""Auth endpoints (OIDC/Authorization Code + PKCE recommended for production)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from packages.security.auth import create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    # TODO: verify credentials against DB, issue JWT
    # Placeholder: accept any login for dev
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Missing credentials")
    token = create_access_token({"sub": req.email, "role": "member"})
    return TokenResponse(access_token=token)

@router.post("/register")
def register(req: LoginRequest):
    # TODO: create user in DB, hash password with argon2id
    return {"status": "registered", "email": req.email}
