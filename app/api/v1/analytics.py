"""
Analytics API Routes

Endpoints for API usage analytics and statistics.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.exceptions import AuthorizationError
from app.utils.api_analytics import get_api_statistics, get_endpoint_statistics, reset_api_statistics, track_api_request
from app.core.analytics import get_event_statistics, track_event
from app.utils.funnel_analysis import get_chart_funnel_analysis, get_reading_funnel_analysis
from database import get_db, User
from auth import get_current_user, get_current_user_optional

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get(
    "/analytics/api-usage",
    summary="Get API Usage Statistics",
    description="""
    Get comprehensive API usage statistics including:
    - Endpoint popularity
    - Response times
    - Error rates
    - User activity
    - IP activity
    
    **Admin only**
    """,
    response_description="API usage statistics",
    tags=["analytics"]
)
async def get_api_usage_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get API usage statistics (admin only).
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    
    try:
        stats = get_api_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting API usage statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.get(
    "/analytics/endpoint/{endpoint:path}",
    summary="Get Endpoint Statistics",
    description="""
    Get statistics for a specific endpoint.
    
    **Admin only**
    """,
    response_description="Endpoint statistics",
    tags=["analytics"]
)
async def get_endpoint_stats_endpoint(
    request: Request,
    endpoint: str,
    method: str = "GET",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get statistics for a specific endpoint (admin only).
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    
    try:
        stats = get_endpoint_statistics(endpoint, method)
        if stats:
            return {
                "status": "success",
                "endpoint": endpoint,
                "method": method,
                "statistics": stats
            }
        else:
            return {
                "status": "not_found",
                "message": f"No statistics found for {method} {endpoint}"
            }
    except Exception as e:
        logger.error(f"Error getting endpoint statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get endpoint statistics: {str(e)}")


@router.post(
    "/analytics/reset",
    summary="Reset API Statistics",
    description="""
    Reset all API usage statistics.
    
    **Admin only**
    """,
    response_description="Reset confirmation",
    tags=["analytics"]
)
async def reset_analytics_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reset API statistics (admin only).
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    
    try:
        reset_api_statistics()
        return {
            "status": "success",
            "message": "API statistics reset successfully"
        }
    except Exception as e:
        logger.error(f"Error resetting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset statistics: {str(e)}")


@router.get(
    "/analytics/events",
    summary="Get Event Statistics",
    description="""
    Get user event statistics and behavior tracking.
    
    **Admin only**
    """,
    response_description="Event statistics",
    tags=["analytics"]
)
async def get_event_statistics_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get event statistics (admin only).
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    
    try:
        stats = get_event_statistics()
        return {
            "status": "success",
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error getting event statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get event statistics: {str(e)}")


@router.post(
    "/analytics/events",
    summary="Track Event",
    description="""
    Track a user event for analytics.
    
    This endpoint allows frontend to track user behavior events.
    """,
    response_description="Event tracking confirmation",
    tags=["analytics"]
)
async def track_event_endpoint(
    request: Request,
    event_type: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Track a user event.
    """
    try:
        user_id = current_user.id if current_user else None
        
        track_event(
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata
        )
        
        return {
            "status": "success",
            "message": "Event tracked successfully"
        }
    except Exception as e:
        logger.error(f"Error tracking event: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to track event: {str(e)}")


@router.get(
    "/analytics/funnel",
    summary="Get Conversion Funnel Analysis",
    description="""
    Get conversion funnel analysis for charts and readings.
    
    Shows conversion rates and identifies drop-off points.
    
    **Admin only**
    """,
    response_description="Funnel analysis",
    tags=["analytics"]
)
async def get_funnel_analysis_endpoint(
    request: Request,
    funnel_type: str = "chart",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get conversion funnel analysis (admin only).
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise AuthorizationError("Admin access required")
    
    try:
        if funnel_type == "chart":
            analysis = get_chart_funnel_analysis()
        elif funnel_type == "reading":
            analysis = get_reading_funnel_analysis()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown funnel type: {funnel_type}. Use 'chart' or 'reading'")
        
        return {
            "status": "success",
            "funnel_type": funnel_type,
            "analysis": analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting funnel analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get funnel analysis: {str(e)}")
