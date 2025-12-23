"""
Admin Analytics Endpoints

Endpoints for admin analytics and system statistics.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.admin_service import AdminService
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/analytics", response_model=Dict[str, Any])
async def get_admin_analytics(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive system statistics and analytics.
    
    Requires admin access.
    """
    try:
        stats = AdminService.get_system_stats(db)
        return stats
    except Exception as e:
        logger.error(f"Error getting admin analytics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics: {str(e)}"
        )

