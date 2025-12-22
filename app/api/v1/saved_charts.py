"""
Saved Charts API Routes

CRUD operations for user's saved charts.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, SavedChart
from auth import get_current_user, User
from app.utils.query_optimization import get_user_charts_optimized, get_chart_with_conversations

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/charts", tags=["saved-charts"])


# Pydantic Models
class SaveChartRequest(BaseModel):
    chart_name: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_location: str
    unknown_time: bool = False
    chart_data_json: Optional[str] = None
    ai_reading: Optional[str] = None
    
    @validator('chart_name')
    def validate_chart_name(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError('Chart name cannot be empty')
        if len(v) > 255:
            raise ValueError('Chart name must be less than 255 characters')
        return v.strip()
    
    @validator('birth_year')
    def validate_year(cls, v):
        if v < 1900 or v > 2100:
            raise ValueError('Birth year must be between 1900 and 2100')
        return v
    
    @validator('birth_month')
    def validate_month(cls, v):
        if v < 1 or v > 12:
            raise ValueError('Birth month must be between 1 and 12')
        return v
    
    @validator('birth_hour')
    def validate_hour(cls, v):
        if v < 0 or v > 23:
            raise ValueError('Hour must be between 0 and 23')
        return v
    
    @validator('birth_minute')
    def validate_minute(cls, v):
        if v < 0 or v > 59:
            raise ValueError('Minute must be between 0 and 59')
        return v
    
    @validator('birth_location')
    def validate_location(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Location must be at least 2 characters')
        if len(v) > 500:
            raise ValueError('Location must be less than 500 characters')
        return v.strip()


class SavedChartResponse(BaseModel):
    id: int
    chart_name: str
    created_at: datetime
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_location: str
    unknown_time: bool
    has_reading: bool

    class Config:
        from_attributes = True


@router.post("/save")
async def save_chart_endpoint(
    data: SaveChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Save a chart for the authenticated user."""
    # Create the saved chart
    saved_chart = SavedChart(
        user_id=current_user.id,
        chart_name=data.chart_name,
        birth_year=data.birth_year,
        birth_month=data.birth_month,
        birth_day=data.birth_day,
        birth_hour=data.birth_hour,
        birth_minute=data.birth_minute,
        birth_location=data.birth_location,
        unknown_time=data.unknown_time,
        chart_data_json=data.chart_data_json,
        ai_reading=data.ai_reading
    )
    db.add(saved_chart)
    db.commit()
    db.refresh(saved_chart)
    
    logger.info(f"Chart saved for user {current_user.email}: {data.chart_name}")
    
    return {
        "id": saved_chart.id,
        "message": "Chart saved successfully."
    }


@router.get("/list")
async def list_charts_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List all saved charts for the authenticated user."""
    # Use optimized query helper
    charts = get_user_charts_optimized(db, current_user.id)
    
    return [
        {
            "id": chart.id,
            "chart_name": chart.chart_name,
            "created_at": chart.created_at.isoformat(),
            "birth_date": f"{chart.birth_month}/{chart.birth_day}/{chart.birth_year}",
            "birth_location": chart.birth_location,
            "unknown_time": chart.unknown_time,
            "has_reading": chart.ai_reading is not None
        }
        for chart in charts
    ]


@router.get("/{chart_id}")
async def get_chart_endpoint(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get a specific saved chart."""
    # Use optimized query with eager loading
    chart = get_chart_with_conversations(db, chart_id, current_user.id)
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    return {
        "id": chart.id,
        "chart_name": chart.chart_name,
        "created_at": chart.created_at.isoformat(),
        "birth_year": chart.birth_year,
        "birth_month": chart.birth_month,
        "birth_day": chart.birth_day,
        "birth_hour": chart.birth_hour,
        "birth_minute": chart.birth_minute,
        "birth_location": chart.birth_location,
        "unknown_time": chart.unknown_time,
        "chart_data": json.loads(chart.chart_data_json) if chart.chart_data_json else None,
        "ai_reading": chart.ai_reading
    }


@router.delete("/{chart_id}")
async def delete_chart_endpoint(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Delete a saved chart."""
    chart = db.query(SavedChart).filter(
        SavedChart.id == chart_id,
        SavedChart.user_id == current_user.id
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    db.delete(chart)
    db.commit()
    
    logger.info(f"Chart deleted for user {current_user.email}: {chart.chart_name} (ID: {chart_id})")
    
    return {"message": "Chart deleted successfully."}

