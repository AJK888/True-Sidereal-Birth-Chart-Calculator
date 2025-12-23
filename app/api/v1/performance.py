"""
Performance Monitoring Endpoints

Endpoints for performance metrics, query statistics, and cache statistics.
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.utils.query_analyzer import get_query_statistics, reset_query_statistics
from app.core.cache_enhancements import get_cache_statistics, reset_cache_statistics
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/queries", response_model=Dict[str, Any])
async def get_query_performance(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get database query performance statistics.
    
    Requires admin access.
    """
    try:
        stats = get_query_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting query statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get query statistics: {str(e)}"
        )


@router.post("/queries/reset")
async def reset_query_stats(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Reset query performance statistics.
    
    Requires admin access.
    """
    try:
        reset_query_statistics()
        return {"message": "Query statistics reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting query statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset query statistics: {str(e)}"
        )


@router.get("/cache", response_model=Dict[str, Any])
async def get_cache_performance(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get cache performance statistics.
    
    Requires admin access.
    """
    try:
        stats = get_cache_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache statistics: {str(e)}"
        )


@router.post("/cache/reset")
async def reset_cache_stats(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Reset cache performance statistics.
    
    Requires admin access.
    """
    try:
        reset_cache_statistics()
        return {"message": "Cache statistics reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting cache statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset cache statistics: {str(e)}"
        )


@router.get("/summary", response_model=Dict[str, Any])
async def get_performance_summary(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive performance summary.
    
    Requires admin access.
    """
    try:
        query_stats = get_query_statistics()
        cache_stats = get_cache_statistics()
        
        return {
            "status": "success",
            "queries": query_stats,
            "cache": cache_stats,
            "recommendations": []
        }
    except Exception as e:
        logger.error(f"Error getting performance summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get performance summary: {str(e)}"
        )

