"""
Mobile API Routes

Mobile-optimized endpoints and PWA support.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.exceptions import NotFoundError
from database import get_db, User, SavedChart
from auth import get_current_user_optional

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["mobile"])


class DeviceRegistrationRequest(BaseModel):
    """Request model for device registration."""
    device_token: str = Field(..., description="Device push notification token")
    device_type: str = Field(..., description="Device type: 'ios', 'android', or 'web'")
    device_id: Optional[str] = Field(None, description="Unique device identifier")


@router.post(
    "/mobile/register-device",
    summary="Register Device for Push Notifications",
    description="""
    Register a device to receive push notifications.
    
    Requires authentication.
    """,
    response_description="Device registration confirmation",
    tags=["mobile"]
)
async def register_device_endpoint(
    request: Request,
    data: DeviceRegistrationRequest,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Register device for push notifications.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # TODO: Store device registration in database
        # For now, return success
        # In production, you would:
        # 1. Create/update device record in database
        # 2. Associate with user
        # 3. Store push token
        
        return {
            "status": "success",
            "message": "Device registered successfully",
            "device_id": data.device_id or f"device_{current_user.id}"
        }
    except Exception as e:
        logger.error(f"Error registering device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to register device: {str(e)}")


@router.post(
    "/mobile/unregister-device",
    summary="Unregister Device",
    description="""
    Unregister a device from push notifications.
    
    Requires authentication.
    """,
    response_description="Device unregistration confirmation",
    tags=["mobile"]
)
async def unregister_device_endpoint(
    request: Request,
    device_id: str,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Unregister device from push notifications.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # TODO: Remove device registration from database
        
        return {
            "status": "success",
            "message": "Device unregistered successfully"
        }
    except Exception as e:
        logger.error(f"Error unregistering device: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unregister device: {str(e)}")


@router.get(
    "/mobile/chart-summary/{chart_hash}",
    summary="Get Mobile-Optimized Chart Summary",
    description="""
    Get a mobile-optimized summary of a chart.
    
    Returns essential chart information in a compact format suitable for mobile displays.
    """,
    response_description="Mobile-optimized chart summary",
    tags=["mobile"]
)
async def get_chart_summary_endpoint(
    request: Request,
    chart_hash: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get mobile-optimized chart summary.
    """
    try:
        # Find chart by hash
        saved_chart = db.query(SavedChart).filter(
            SavedChart.chart_data_json.contains(f'"chart_hash":"{chart_hash}"')
        ).first()
        
        if not saved_chart:
            raise NotFoundError(
                detail="Chart not found",
                resource_type="chart",
                resource_id=chart_hash
            )
        
        # Parse chart data
        import json
        chart_data = json.loads(saved_chart.chart_data_json)
        
        # Extract essential information for mobile
        sidereal_placements = chart_data.get("sidereal_placements", {})
        tropical_placements = chart_data.get("tropical_placements", {})
        
        # Get key placements (Sun, Moon, Rising)
        key_placements = {}
        for system_name, placements in [("sidereal", sidereal_placements), ("tropical", tropical_placements)]:
            key_placements[system_name] = {}
            for planet in ["Sun", "Moon", "Ascendant"]:
                if planet in placements:
                    key_placements[system_name][planet] = placements[planet]
        
        return {
            "status": "success",
            "chart_hash": chart_hash,
            "chart_name": saved_chart.chart_name,
            "key_placements": key_placements,
            "numerology": chart_data.get("numerology", {}),
            "chinese_zodiac": chart_data.get("chinese_zodiac", {}),
            "summary": {
                "has_reading": bool(saved_chart.ai_reading),
                "created_at": saved_chart.created_at.isoformat() if saved_chart.created_at else None
            }
        }
    
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error getting chart summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get chart summary: {str(e)}")

