"""
Analytics and reporting API endpoints.

Provides usage analytics, performance metrics, and business intelligence.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import get_current_user
from app.services.analytics_service import (
    get_usage_statistics, get_user_activity,
    get_endpoint_metrics, get_event_counts
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Pydantic Models
class UsageStatisticsResponse(BaseModel):
    """Schema for usage statistics response."""
    total_events: int
    events_by_type: Dict[str, int]
    unique_users_count: int
    events_by_day: Dict[str, int]
    start_date: Optional[str]
    end_date: Optional[str]


class UserActivityResponse(BaseModel):
    """Schema for user activity response."""
    user_id: int
    total_events: int
    events_by_type: Dict[str, int]
    first_activity: Optional[str]
    last_activity: Optional[str]


class EndpointMetricsResponse(BaseModel):
    """Schema for endpoint metrics response."""
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    requests_by_day: Dict[str, int]
    requests_by_hour: Dict[int, int]


@router.get("/usage", response_model=UsageStatisticsResponse)
async def get_usage_stats(
    days: int = Query(30, description="Number of days to include", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get overall usage statistics.
    
    Requires authentication. Returns aggregated usage metrics.
    """
    # Only admins can view overall statistics
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    stats = get_usage_statistics(start_date=start_date, end_date=end_date)
    
    return UsageStatisticsResponse(
        total_events=stats["total_events"],
        events_by_type=stats["events_by_type"],
        unique_users_count=stats["unique_users_count"],
        events_by_day=stats["events_by_day"],
        start_date=stats["start_date"],
        end_date=stats["end_date"]
    )


@router.get("/user/{user_id}", response_model=UserActivityResponse)
async def get_user_analytics(
    user_id: int,
    days: int = Query(30, description="Number of days to include", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics for a specific user.
    
    Users can only view their own analytics unless they are admins.
    """
    # Check authorization
    if current_user.id != user_id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    activity = get_user_activity(user_id, start_date=start_date, end_date=end_date)
    
    return UserActivityResponse(
        user_id=activity["user_id"],
        total_events=activity["total_events"],
        events_by_type=activity["events_by_type"],
        first_activity=activity["first_activity"].isoformat() if activity["first_activity"] else None,
        last_activity=activity["last_activity"].isoformat() if activity["last_activity"] else None
    )


@router.get("/endpoint/{endpoint:path}", response_model=EndpointMetricsResponse)
async def get_endpoint_analytics(
    endpoint: str,
    days: int = Query(30, description="Number of days to include", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get metrics for a specific endpoint.
    
    Requires admin access.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    metrics = get_endpoint_metrics(endpoint, start_date=start_date, end_date=end_date)
    
    return EndpointMetricsResponse(
        endpoint=metrics["endpoint"],
        total_requests=metrics["total_requests"],
        successful_requests=metrics["successful_requests"],
        failed_requests=metrics["failed_requests"],
        average_response_time=metrics["average_response_time"],
        requests_by_day=metrics["requests_by_day"],
        requests_by_hour=metrics["requests_by_hour"]
    )


@router.get("/events/{event_type}")
async def get_event_analytics(
    event_type: str,
    days: int = Query(30, description="Number of days to include", ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics for a specific event type.
    
    Requires admin access.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    count = get_event_counts(event_type, start_date=start_date, end_date=end_date)
    
    return {
        "event_type": event_type,
        "count": count,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat()
    }

