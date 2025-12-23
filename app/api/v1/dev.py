"""
Development Endpoints

Endpoints for development and debugging (development mode only).
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.utils.dev_tools import (
    is_development, get_environment_info, get_config_info, debug_request
)
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter(prefix="/dev", tags=["dev"])


def require_development():
    """Dependency to require development mode."""
    def dev_checker(
        current_user: User = Depends(require_admin())
    ) -> User:
        if not is_development():
            raise HTTPException(
                status_code=403,
                detail="This endpoint is only available in development mode"
            )
        return current_user
    return dev_checker


@router.get("/environment", response_model=Dict[str, Any])
async def get_environment(
    current_user: User = Depends(require_development()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get environment information.
    
    Development mode only. Requires admin access.
    """
    try:
        return {
            "status": "success",
            "environment": get_environment_info(),
            "config": get_config_info()
        }
    except Exception as e:
        logger.error(f"Error getting environment info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get environment info: {str(e)}"
        )


@router.get("/request", response_model=Dict[str, Any])
async def debug_request_endpoint(
    request: Request,
    current_user: User = Depends(require_development()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get debug information about the current request.
    
    Development mode only. Requires admin access.
    """
    try:
        debug_info = debug_request(request)
        return {
            "status": "success",
            "request": debug_info
        }
    except Exception as e:
        logger.error(f"Error getting request debug info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get request debug info: {str(e)}"
        )


@router.get("/metrics/reset", response_model=Dict[str, str])
async def reset_all_metrics(
    current_user: User = Depends(require_development()),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Reset all metrics (development only).
    
    Development mode only. Requires admin access.
    """
    try:
        from app.core.advanced_metrics import metrics_collector
        from app.utils.query_analyzer import reset_query_statistics
        from app.core.cache_enhancements import reset_cache_statistics
        
        metrics_collector.reset()
        reset_query_statistics()
        reset_cache_statistics()
        
        return {"message": "All metrics reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset metrics: {str(e)}"
        )

