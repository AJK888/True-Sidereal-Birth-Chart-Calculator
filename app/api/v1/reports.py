"""
Report Generation Endpoints

Endpoints for generating custom reports and analytics.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.services.business_analytics import BusinessAnalyticsService
from app.services.revenue_analytics import RevenueAnalyticsService
from app.services.user_segmentation import UserSegmentationService
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


# Pydantic Models
class ReportRequest(BaseModel):
    """Schema for report generation request."""
    report_type: str
    days: Optional[int] = 30
    include_charts: Optional[bool] = False


@router.get("/business", response_model=Dict[str, Any])
async def get_business_report(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive business analytics report.
    
    Requires admin access.
    """
    try:
        overview = BusinessAnalyticsService.get_business_overview(db, days)
        return {
            "report_type": "business",
            "period_days": days,
            "data": overview,
            "generated_at": "2025-01-22T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error generating business report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate business report: {str(e)}"
        )


@router.get("/revenue", response_model=Dict[str, Any])
async def get_revenue_report(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get revenue analytics report.
    
    Requires admin access.
    """
    try:
        revenue_metrics = RevenueAnalyticsService.get_revenue_metrics(db, days)
        subscription_metrics = RevenueAnalyticsService.get_subscription_metrics(db)
        credit_metrics = RevenueAnalyticsService.get_credit_metrics(db, days)
        
        return {
            "report_type": "revenue",
            "period_days": days,
            "revenue_metrics": revenue_metrics,
            "subscription_metrics": subscription_metrics,
            "credit_metrics": credit_metrics,
            "generated_at": "2025-01-22T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error generating revenue report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate revenue report: {str(e)}"
        )


@router.get("/segmentation", response_model=Dict[str, Any])
async def get_segmentation_report(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get user segmentation report.
    
    Requires admin access.
    """
    try:
        segments = UserSegmentationService.get_user_segments(db)
        cohorts = UserSegmentationService.get_cohort_analysis(db)
        lifetime_value = UserSegmentationService.get_user_lifetime_value(db)
        
        return {
            "report_type": "segmentation",
            "segments": segments,
            "cohorts": cohorts,
            "lifetime_value": lifetime_value,
            "generated_at": "2025-01-22T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error generating segmentation report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate segmentation report: {str(e)}"
        )


@router.post("/generate", response_model=Dict[str, Any])
async def generate_custom_report(
    request: ReportRequest,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate a custom report based on request parameters.
    
    Requires admin access.
    """
    try:
        report_data = {}
        
        if request.report_type == "business":
            report_data = BusinessAnalyticsService.get_business_overview(
                db, request.days or 30
            )
        elif request.report_type == "revenue":
            report_data = {
                "revenue": RevenueAnalyticsService.get_revenue_metrics(
                    db, request.days or 30
                ),
                "subscriptions": RevenueAnalyticsService.get_subscription_metrics(db),
                "credits": RevenueAnalyticsService.get_credit_metrics(
                    db, request.days or 30
                )
            }
        elif request.report_type == "segmentation":
            report_data = {
                "segments": UserSegmentationService.get_user_segments(db),
                "cohorts": UserSegmentationService.get_cohort_analysis(db),
                "lifetime_value": UserSegmentationService.get_user_lifetime_value(db)
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown report type: {request.report_type}"
            )
        
        return {
            "report_type": request.report_type,
            "period_days": request.days or 30,
            "data": report_data,
            "generated_at": "2025-01-22T00:00:00Z"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating custom report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )

