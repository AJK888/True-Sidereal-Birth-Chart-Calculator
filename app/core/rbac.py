"""
Role-Based Access Control (RBAC) System

Provides role-based permissions and access control for admin features.
"""

from typing import Optional, List
from enum import Enum
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from database import User, get_db
from auth import get_current_user


class Role(str, Enum):
    """User roles in the system."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"
    ANALYST = "analyst"


class Permission(str, Enum):
    """System permissions."""
    # User management
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    
    # Chart management
    VIEW_ALL_CHARTS = "view_all_charts"
    MODERATE_CHARTS = "moderate_charts"
    DELETE_CHARTS = "delete_charts"
    
    # Analytics
    VIEW_ANALYTICS = "view_analytics"
    VIEW_REVENUE = "view_revenue"
    EXPORT_DATA = "export_data"
    
    # System
    VIEW_SYSTEM_CONFIG = "view_system_config"
    EDIT_SYSTEM_CONFIG = "edit_system_config"
    VIEW_AUDIT_LOGS = "view_audit_logs"


# Role to permissions mapping
ROLE_PERMISSIONS = {
    Role.USER: [],
    Role.MODERATOR: [
        Permission.VIEW_ALL_CHARTS,
        Permission.MODERATE_CHARTS,
        Permission.VIEW_ANALYTICS,
    ],
    Role.ANALYST: [
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_REVENUE,
        Permission.EXPORT_DATA,
        Permission.VIEW_ALL_CHARTS,
    ],
    Role.ADMIN: list(Permission),  # Admins have all permissions
}


def get_user_role(user: User) -> Role:
    """Get the role for a user."""
    if user.is_admin:
        return Role.ADMIN
    # Future: Add role field to User model for more granular roles
    return Role.USER


def has_permission(user: User, permission: Permission) -> bool:
    """Check if a user has a specific permission."""
    role = get_user_role(user)
    return permission in ROLE_PERMISSIONS.get(role, [])


def require_permission(permission: Permission):
    """Dependency to require a specific permission."""
    def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission.value} required"
            )
        return current_user
    return permission_checker


def require_admin():
    """Dependency to require admin role."""
    def admin_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        return current_user
    return admin_checker


def get_user_permissions(user: User) -> List[Permission]:
    """Get all permissions for a user."""
    role = get_user_role(user)
    return ROLE_PERMISSIONS.get(role, [])

