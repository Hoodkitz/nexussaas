"""OIDC callback endpoints."""
from fastapi import APIRouter, HTTPException
from packages.security.oidc import get_authorization_url, exchange_code, get_user_info
from packages.security.auth import create_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.get("/google")
def google_login():
    url = get_authorization_url()
    return {"authorization_url": url}

@router.get("/callback")
async def google_callback(code: str, state: str = None):
    try:
        tokens = await exchange_code(code)
        user_info = await get_user_info(tokens["access_token"])
        # TODO: find or create user in DB, assign tenant membership
        jwt_token = create_access_token({
            "sub": user_info["email"],
            "name": user_info.get("name"),
            "role": "member",
        })
        return {"access_token": jwt_token, "token_type": "bearer", "user": user_info}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
