"""Data export and deletion endpoints (DSGVO Art. 15, 17)."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/me/export")
def export_user_data():
    # TODO: collect all user data across tenants, return as JSON
    return {"status": "export_requested", "download_url": None}

@router.delete("/me")
def delete_user():
    # TODO: create deletion job, soft-delete user
    return {"status": "deletion_requested", "estimated_completion": "30 days"}
