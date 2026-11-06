"""Role-based access control."""
from packages.domain.user import UserRole

PERMISSIONS = {
    UserRole.OWNER: {"read", "write", "delete", "admin", "billing"},
    UserRole.ADMIN: {"read", "write", "delete", "admin"},
    UserRole.MEMBER: {"read", "write"},
    UserRole.VIEWER: {"read"},
}

def has_permission(role: UserRole, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
