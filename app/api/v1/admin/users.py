"""
Admin User Management Endpoints

Endpoints for managing users (list, view, update, delete).
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.admin_service import AdminService
from database import get_db, User
from auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter()


# Pydantic Models
class UserUpdateRequest(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    credits: Optional[int] = None


class UserListResponse(BaseModel):
    """Schema for user list response."""
    users: list
    total: int
    skip: int
    limit: int


class UserStatsResponse(BaseModel):
    """Schema for user statistics response."""
    user: dict
    stats: dict
    recent_credit_transactions: list


# Endpoints
@router.get("/users", response_model=Dict[str, Any])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    sort_by: str = Query("created_at", regex="^(created_at|email|full_name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all users with optional filtering and pagination.
    
    Requires admin access.
    """
    try:
        result = AdminService.get_users(
            db=db,
            skip=skip,
            limit=limit,
            search=search,
            is_active=is_active,
            is_admin=is_admin,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert users to dict format
        users_data = []
        for user in result["users"]:
            users_data.append({
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "is_active": user.is_active,
                "is_admin": user.is_admin,
                "credits": user.credits,
                "subscription_status": user.subscription_status,
            })
        
        return {
            "users": users_data,
            "total": result["total"],
            "skip": result["skip"],
            "limit": result["limit"]
        }
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list users: {str(e)}"
        )


@router.get("/users/{user_id}", response_model=Dict[str, Any])
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific user including statistics.
    
    Requires admin access.
    """
    try:
        stats = AdminService.get_user_stats(db, user_id)
        if not stats:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Convert user to dict
        user_data = {
            "id": stats["user"].id,
            "email": stats["user"].email,
            "full_name": stats["user"].full_name,
            "created_at": stats["user"].created_at.isoformat() if stats["user"].created_at else None,
            "is_active": stats["user"].is_active,
            "is_admin": stats["user"].is_admin,
            "credits": stats["user"].credits,
            "subscription_status": stats["user"].subscription_status,
            "stripe_customer_id": stats["user"].stripe_customer_id,
            "subscription_start_date": stats["user"].subscription_start_date.isoformat() if stats["user"].subscription_start_date else None,
            "subscription_end_date": stats["user"].subscription_end_date.isoformat() if stats["user"].subscription_end_date else None,
        }
        
        # Convert credit transactions
        transactions_data = []
        for tx in stats["recent_credit_transactions"]:
            transactions_data.append({
                "id": tx.id,
                "transaction_type": tx.transaction_type,
                "credits": tx.credits,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            })
        
        return {
            "user": user_data,
            "stats": stats["stats"],
            "recent_credit_transactions": transactions_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user: {str(e)}"
        )


@router.put("/users/{user_id}", response_model=Dict[str, Any])
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update user information.
    
    Requires admin access.
    """
    try:
        updated_user = AdminService.update_user(
            db=db,
            user_id=user_id,
            email=data.email,
            full_name=data.full_name,
            is_active=data.is_active,
            is_admin=data.is_admin,
            credits=data.credits
        )
        
        return {
            "id": updated_user.id,
            "email": updated_user.email,
            "full_name": updated_user.full_name,
            "is_active": updated_user.is_active,
            "is_admin": updated_user.is_admin,
            "credits": updated_user.credits,
            "message": "User updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update user: {str(e)}"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a user and all associated data.
    
    Requires admin access.
    """
    try:
        # Prevent self-deletion
        if user_id == current_user.id:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete your own account"
            )
        
        AdminService.delete_user(db, user_id)
        
        return {"message": f"User {user_id} deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user: {str(e)}"
        )

