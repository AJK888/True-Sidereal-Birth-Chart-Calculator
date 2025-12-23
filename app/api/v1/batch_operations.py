"""
Batch Operations Endpoints

Endpoints for performing batch operations on multiple resources.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from database import get_db, User, SavedChart

logger = setup_logger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


# Pydantic Models
class BatchDeleteRequest(BaseModel):
    """Schema for batch delete request."""
    ids: List[int]
    resource_type: str  # "users", "charts", "conversations"


class BatchUpdateRequest(BaseModel):
    """Schema for batch update request."""
    ids: List[int]
    resource_type: str
    updates: Dict[str, Any]


class BatchOperationResponse(BaseModel):
    """Schema for batch operation response."""
    success: bool
    processed: int
    succeeded: int
    failed: int
    errors: List[Dict[str, Any]]


@router.post("/delete", response_model=Dict[str, Any])
async def batch_delete(
    request: BatchDeleteRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete multiple resources in a single operation.
    
    Requires admin access.
    """
    if len(request.ids) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 items can be deleted in a single batch"
        )
    
    succeeded = 0
    failed = 0
    errors = []
    
    try:
        if request.resource_type == "charts":
            for chart_id in request.ids:
                try:
                    chart = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
                    if chart:
                        db.delete(chart)
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append({
                            "id": chart_id,
                            "error": "Chart not found"
                        })
                except Exception as e:
                    failed += 1
                    errors.append({
                        "id": chart_id,
                        "error": str(e)
                    })
            
            db.commit()
        
        elif request.resource_type == "users":
            # Prevent self-deletion
            if current_user.id in request.ids:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete your own account"
                )
            
            for user_id in request.ids:
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        db.delete(user)
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append({
                            "id": user_id,
                            "error": "User not found"
                        })
                except Exception as e:
                    failed += 1
                    errors.append({
                        "id": user_id,
                        "error": str(e)
                    })
            
            db.commit()
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported resource type: {request.resource_type}"
            )
        
        return {
            "success": failed == 0,
            "processed": len(request.ids),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch delete: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch delete failed: {str(e)}"
        )


@router.post("/update", response_model=Dict[str, Any])
async def batch_update(
    request: BatchUpdateRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update multiple resources in a single operation.
    
    Requires admin access.
    """
    if len(request.ids) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 items can be updated in a single batch"
        )
    
    succeeded = 0
    failed = 0
    errors = []
    
    try:
        if request.resource_type == "charts":
            for chart_id in request.ids:
                try:
                    chart = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
                    if chart:
                        # Apply updates
                        for key, value in request.updates.items():
                            if hasattr(chart, key):
                                setattr(chart, key, value)
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append({
                            "id": chart_id,
                            "error": "Chart not found"
                        })
                except Exception as e:
                    failed += 1
                    errors.append({
                        "id": chart_id,
                        "error": str(e)
                    })
            
            db.commit()
        
        elif request.resource_type == "users":
            for user_id in request.ids:
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        # Apply updates (with validation)
                        allowed_fields = ["is_active", "credits", "full_name"]
                        for key, value in request.updates.items():
                            if key in allowed_fields and hasattr(user, key):
                                setattr(user, key, value)
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append({
                            "id": user_id,
                            "error": "User not found"
                        })
                except Exception as e:
                    failed += 1
                    errors.append({
                        "id": user_id,
                        "error": str(e)
                    })
            
            db.commit()
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported resource type: {request.resource_type}"
            )
        
        return {
            "success": failed == 0,
            "processed": len(request.ids),
            "succeeded": succeeded,
            "failed": failed,
            "errors": errors
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch update: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch update failed: {str(e)}"
        )


@router.get("/status", response_model=Dict[str, Any])
async def get_batch_status(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get batch operation status and limits.
    
    Requires admin access.
    """
    return {
        "max_batch_size": 100,
        "supported_operations": ["delete", "update"],
        "supported_resources": ["users", "charts"],
        "timestamp": "2025-01-22T00:00:00Z"
    }

