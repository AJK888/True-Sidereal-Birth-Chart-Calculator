"""
Admin System Configuration Endpoints

Endpoints for system configuration and management.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from app.core.rbac import require_admin
from app.core.security_audit import SecurityAuditor
from app.config import (
    API_BASE_URL, DATABASE_URL, SECRET_KEY, GEMINI_API_KEY,
    SENDGRID_API_KEY, STRIPE_SECRET_KEY, ADMIN_EMAIL
)
from database import get_db, User

logger = setup_logger(__name__)

router = APIRouter()


class SystemConfigResponse(BaseModel):
    """Schema for system configuration response."""
    api_base_url: str
    database_configured: bool
    secret_key_configured: bool
    gemini_configured: bool
    sendgrid_configured: bool
    stripe_configured: bool
    admin_email: Optional[str]
    # Don't expose sensitive values, just whether they're configured


@router.get("/system/config", response_model=Dict[str, Any])
async def get_system_config(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get system configuration status (without exposing sensitive values).
    
    Requires admin access.
    """
    try:
        return {
            "api_base_url": API_BASE_URL,
            "database_configured": bool(DATABASE_URL and DATABASE_URL != "sqlite:///./astrology.db"),
            "secret_key_configured": bool(SECRET_KEY and SECRET_KEY != "your-secret-key-change-in-production"),
            "gemini_configured": bool(GEMINI_API_KEY),
            "sendgrid_configured": bool(SENDGRID_API_KEY),
            "stripe_configured": bool(STRIPE_SECRET_KEY),
            "admin_email": ADMIN_EMAIL,
            "timestamp": "2025-01-22T00:00:00Z"  # Could use actual timestamp
        }
    except Exception as e:
        logger.error(f"Error getting system config: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system config: {str(e)}"
        )


@router.get("/system/health", response_model=Dict[str, Any])
async def get_system_health(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get detailed system health information.
    
    Requires admin access.
    """
    try:
        # Test database connection
        db_status = "healthy"
        try:
            db.execute("SELECT 1")
        except Exception:
            db_status = "unhealthy"
        
        # Check configuration
        config_status = {
            "database": db_status,
            "gemini": "configured" if GEMINI_API_KEY else "not_configured",
            "sendgrid": "configured" if SENDGRID_API_KEY else "not_configured",
            "stripe": "configured" if STRIPE_SECRET_KEY else "not_configured",
        }
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "components": config_status,
            "timestamp": "2025-01-22T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system health: {str(e)}"
        )


@router.get("/system/security", response_model=Dict[str, Any])
async def get_security_status(
    current_user: User = Depends(require_admin()),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get security audit status and recommendations.
    
    Requires admin access.
    """
    try:
        security_status = SecurityAuditor.get_security_status()
        return security_status
    except Exception as e:
        logger.error(f"Error getting security status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get security status: {str(e)}"
        )

