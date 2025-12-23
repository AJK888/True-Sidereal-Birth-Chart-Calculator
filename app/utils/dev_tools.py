"""
Development Tools

Utilities and helpers for development and debugging.
"""

import logging
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


def is_development() -> bool:
    """Check if running in development mode."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    return env in ["development", "dev", "local"]


def is_production() -> bool:
    """Check if running in production mode."""
    env = os.getenv("ENVIRONMENT", "production").lower()
    return env == "production"


def get_environment_info() -> Dict[str, Any]:
    """Get environment information."""
    return {
        "environment": os.getenv("ENVIRONMENT", "production"),
        "is_development": is_development(),
        "is_production": is_production(),
        "python_version": sys.version,
        "timestamp": datetime.utcnow().isoformat()
    }


def get_config_info() -> Dict[str, Any]:
    """Get configuration information (without sensitive values)."""
    from app.config import (
        API_BASE_URL, DATABASE_URL, GEMINI_API_KEY,
        SENDGRID_API_KEY, STRIPE_SECRET_KEY, ADMIN_EMAIL
    )
    
    return {
        "api_base_url": API_BASE_URL,
        "database_configured": bool(DATABASE_URL and DATABASE_URL != "sqlite:///./astrology.db"),
        "gemini_configured": bool(GEMINI_API_KEY),
        "sendgrid_configured": bool(SENDGRID_API_KEY),
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "admin_email": ADMIN_EMAIL,
        "timestamp": datetime.utcnow().isoformat()
    }


def debug_request(request: Any) -> Dict[str, Any]:
    """Get debug information about a request."""
    return {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client": {
            "host": request.client.host if request.client else None,
            "port": request.client.port if request.client else None,
        }
    }
