"""Role-based access control."""
from packages.domain.models import UserRole

PERMISSIONS: dict[str, set[str]] = {
    UserRole.OWNER.value: {"read", "write", "approve", "admin", "billing", "delete_tenant"},
    UserRole.ADMIN.value: {"read", "write", "approve", "admin"},
    UserRole.MEMBER.value: {"read", "write"},
    UserRole.VIEWER.value: {"read"},
}
ROLE_RANK = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(str(getattr(role, "value", role)), set())
