"""
Admin Chart Management Endpoints

Endpoints for managing and moderating charts.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.admin_service import AdminService
from database import get_db, User, SavedChart

logger = setup_logger(__name__)

router = APIRouter()


@router.get("/charts", response_model=Dict[str, Any])
async def list_all_charts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|chart_name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    List all charts with optional filtering and pagination.
    
    Requires admin access.
    """
    try:
        result = AdminService.get_all_charts(
            db=db,
            skip=skip,
            limit=limit,
            user_id=user_id,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Convert charts to dict format
        charts_data = []
        for chart in result["charts"]:
            charts_data.append({
                "id": chart.id,
                "user_id": chart.user_id,
                "chart_name": chart.chart_name,
                "created_at": chart.created_at.isoformat() if chart.created_at else None,
                "birth_year": chart.birth_year,
                "birth_month": chart.birth_month,
                "birth_day": chart.birth_day,
                "birth_location": chart.birth_location,
                "has_reading": bool(chart.ai_reading),
            })
        
        return {
            "charts": charts_data,
            "total": result["total"],
            "skip": result["skip"],
            "limit": result["limit"]
        }
    except Exception as e:
        logger.error(f"Error listing charts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list charts: {str(e)}"
        )


@router.get("/charts/{chart_id}", response_model=Dict[str, Any])
async def get_chart_details(
    chart_id: int,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific chart.
    
    Requires admin access.
    """
    try:
        chart = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        # Get user information
        user = db.query(User).filter(User.id == chart.user_id).first()
        
        return {
            "id": chart.id,
            "user": {
                "id": user.id if user else None,
                "email": user.email if user else None,
            },
            "chart_name": chart.chart_name,
            "created_at": chart.created_at.isoformat() if chart.created_at else None,
            "birth_data": {
                "year": chart.birth_year,
                "month": chart.birth_month,
                "day": chart.birth_day,
                "hour": chart.birth_hour,
                "minute": chart.birth_minute,
                "location": chart.birth_location,
                "unknown_time": chart.unknown_time,
            },
            "has_chart_data": bool(chart.chart_data_json),
            "has_reading": bool(chart.ai_reading),
            "reading_length": len(chart.ai_reading) if chart.ai_reading else 0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chart {chart_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chart: {str(e)}"
        )


@router.delete("/charts/{chart_id}")
async def delete_chart(
    chart_id: int,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a chart.
    
    Requires admin access.
    """
    try:
        chart = db.query(SavedChart).filter(SavedChart.id == chart_id).first()
        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        db.delete(chart)
        db.commit()
        
        logger.info(f"Chart {chart_id} deleted by admin {current_user.id}")
        
        return {"message": f"Chart {chart_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chart {chart_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete chart: {str(e)}"
        )

