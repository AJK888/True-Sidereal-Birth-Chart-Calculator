"""
Advanced Monitoring Endpoints

Endpoints for advanced monitoring, metrics, alerts, and error tracking.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.core.advanced_metrics import metrics_collector
from app.services.alerting import alerting_service, AlertSeverity
from app.utils.error_aggregator import error_aggregator
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics", response_model=Dict[str, Any])
async def get_advanced_metrics(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get advanced metrics summary.
    
    Requires admin access.
    """
    try:
        summary = metrics_collector.get_summary()
        return {
            "status": "success",
            "metrics": summary
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/metrics/requests", response_model=Dict[str, Any])
async def get_request_metrics(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get request-level metrics.
    
    Requires admin access.
    """
    try:
        metrics = metrics_collector.get_request_metrics()
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Error getting request metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get request metrics: {str(e)}"
        )


@router.get("/metrics/endpoints", response_model=Dict[str, Any])
async def get_endpoint_metrics(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get endpoint-level metrics.
    
    Requires admin access.
    """
    try:
        metrics = metrics_collector.get_endpoint_metrics()
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Error getting endpoint metrics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get endpoint metrics: {str(e)}"
        )


@router.get("/alerts", response_model=Dict[str, Any])
async def get_alerts(
    severity: Optional[str] = Query(None, regex="^(info|warning|error|critical)$"),
    resolved: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get alerts with optional filtering.
    
    Requires admin access.
    """
    try:
        alert_severity = AlertSeverity(severity) if severity else None
        alerts = alerting_service.get_alerts(
            severity=alert_severity,
            resolved=resolved,
            limit=limit
        )
        
        alerts_data = [
            {
                "id": alert.id,
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "source": alert.source,
                "created_at": alert.created_at.isoformat(),
                "resolved": alert.resolved,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "metadata": alert.metadata
            }
            for alert in alerts
        ]
        
        return {
            "status": "success",
            "alerts": alerts_data,
            "count": len(alerts_data),
            "summary": alerting_service.get_alert_summary()
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get alerts: {str(e)}"
        )


@router.post("/alerts/check", response_model=Dict[str, Any])
async def check_alerts(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check metrics against thresholds and generate alerts.
    
    Requires admin access.
    """
    try:
        new_alerts = alerting_service.check_thresholds()
        return {
            "status": "success",
            "alerts_generated": len(new_alerts),
            "alerts": [
                {
                    "id": alert.id,
                    "title": alert.title,
                    "severity": alert.severity.value
                }
                for alert in new_alerts
            ]
        }
    except Exception as e:
        logger.error(f"Error checking alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check alerts: {str(e)}"
        )


@router.post("/alerts/{alert_id}/resolve", response_model=Dict[str, Any])
async def resolve_alert(
    alert_id: str,
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Resolve an alert.
    
    Requires admin access.
    """
    try:
        success = alerting_service.resolve_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": f"Alert {alert_id} resolved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve alert: {str(e)}"
        )


@router.get("/errors", response_model=Dict[str, Any])
async def get_error_summary(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get error summary and aggregation.
    
    Requires admin access.
    """
    try:
        summary = error_aggregator.get_error_summary(hours=hours)
        return {
            "status": "success",
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Error getting error summary: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get error summary: {str(e)}"
        )


@router.get("/errors/top", response_model=Dict[str, Any])
async def get_top_errors(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get top errors by frequency.
    
    Requires admin access.
    """
    try:
        top_errors = error_aggregator.get_top_errors(limit=limit)
        return {
            "status": "success",
            "top_errors": top_errors
        }
    except Exception as e:
        logger.error(f"Error getting top errors: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get top errors: {str(e)}"
        )


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_monitoring_dashboard(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive monitoring dashboard data.
    
    Requires admin access.
    """
    try:
        metrics = metrics_collector.get_summary()
        alerts_summary = alerting_service.get_alert_summary()
        error_summary = error_aggregator.get_error_summary(hours=24)
        
        return {
            "status": "success",
            "dashboard": {
                "metrics": metrics,
                "alerts": alerts_summary,
                "errors": error_summary,
                "timestamp": "2025-01-22T00:00:00Z"
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard data: {str(e)}"
        )

