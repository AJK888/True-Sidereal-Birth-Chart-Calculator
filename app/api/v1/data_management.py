"""
Data Management Endpoints

Endpoints for data export, import, and GDPR compliance.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin, require_permission, Permission
from app.services.data_export import DataExportService
from app.services.gdpr_service import GDPRService
from database import get_db, User
from auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter(prefix="/data", tags=["data-management"])


# Pydantic Models
class GDPRExportRequest(BaseModel):
    """Schema for GDPR data export request."""
    user_id: int


class GDPRDeleteRequest(BaseModel):
    """Schema for GDPR data deletion request."""
    user_id: int
    confirm: bool = False


@router.get("/export/user/{user_id}/json")
async def export_user_data_json(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Export user data as JSON.
    
    Users can export their own data, admins can export any user's data.
    """
    try:
        # Check if user is requesting their own data or is admin
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You can only export your own data"
            )
        
        export_data = DataExportService.export_user_data_json(db, user_id)
        return export_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export user data: {str(e)}"
        )


@router.get("/export/user/{user_id}/csv")
async def export_user_data_csv(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export user data as CSV.
    
    Users can export their own data, admins can export any user's data.
    """
    try:
        # Check if user is requesting their own data or is admin
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You can only export your own data"
            )
        
        csv_data = DataExportService.export_user_data_csv(db, user_id)
        
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=user_{user_id}_data.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting user data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export user data: {str(e)}"
        )


@router.get("/export/gdpr/{user_id}")
async def export_gdpr_data(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Export user data in GDPR-compliant format.
    
    Users can export their own data, admins can export any user's data.
    """
    try:
        # Check if user is requesting their own data or is admin
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You can only export your own data"
            )
        
        export_data = GDPRService.export_user_data_gdpr(db, user_id)
        return export_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting GDPR data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export GDPR data: {str(e)}"
        )


@router.delete("/gdpr/user/{user_id}")
async def delete_user_data_gdpr(
    user_id: int,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Delete all user data in compliance with GDPR right to erasure.
    
    Users can delete their own data, admins can delete any user's data.
    WARNING: This action is irreversible!
    """
    try:
        if not confirm:
            raise HTTPException(
                status_code=400,
                detail="Deletion requires confirmation. Set confirm=true"
            )
        
        # Check if user is deleting their own data or is admin
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own data"
            )
        
        result = GDPRService.delete_user_data_gdpr(db, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting GDPR data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete user data: {str(e)}"
        )


@router.get("/export/users/csv")
async def export_all_users_csv(
    include_inactive: bool = Query(False),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Export all users as CSV.
    
    Requires admin access.
    """
    try:
        csv_data = DataExportService.export_all_users_csv(db, include_inactive)
        
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=all_users.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export users: {str(e)}"
        )


@router.get("/export/charts/csv")
async def export_charts_csv(
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Export charts as CSV.
    
    Requires admin access.
    """
    try:
        csv_data = DataExportService.export_charts_csv(db, user_id)
        
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=charts.csv"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting charts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export charts: {str(e)}"
        )


@router.get("/gdpr/status")
async def get_gdpr_status(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get GDPR compliance status.
    
    Requires admin access.
    """
    try:
        status = GDPRService.get_gdpr_compliance_status(db)
        return status
    except Exception as e:
        logger.error(f"Error getting GDPR status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get GDPR status: {str(e)}"
        )

