"""
Utilities API Routes

Health check, ping, diagnostic endpoints, and utility functions.
"""

import os
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from app.core.logging_config import setup_logger
# Limiter will be set from main app - create placeholder for decorators
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    # Placeholder limiter for decorators - actual limiter set from app.state.limiter at runtime
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    # Dummy limiter if slowapi not available (for development/testing)
    class _DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = _DummyLimiter()

logger = setup_logger(__name__)

# Create router - root endpoints have no prefix, log-clicks is under /api
router = APIRouter(tags=["utilities"])

# Create separate router for /api endpoints
api_router = APIRouter(prefix="/api", tags=["utilities"])

# Import centralized configuration
from app.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL

# Import monitoring utilities
from app.utils.metrics import get_health_metrics


@router.api_route("/ping", methods=["GET", "HEAD"])
def ping() -> Dict[str, str]:
    """Ping endpoint for health checks."""
    return {"message": "ok"}


@router.get("/")
def root() -> Dict[str, str]:
    """Simple root endpoint so uptime monitors don't hit a 404."""
    return {"message": "ok"}


@router.get("/check_email_config")
def check_email_config() -> Dict[str, Any]:
    """Diagnostic endpoint to check SendGrid email configuration."""
    config_status = {
        "sendgrid_api_key": {
            "configured": bool(SENDGRID_API_KEY),
            "length": len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 0,
            "preview": f"{SENDGRID_API_KEY[:10]}..." if SENDGRID_API_KEY and len(SENDGRID_API_KEY) > 10 else "Not set"
        },
        "sendgrid_from_email": {
            "configured": bool(SENDGRID_FROM_EMAIL),
            "value": SENDGRID_FROM_EMAIL if SENDGRID_FROM_EMAIL else "Not set"
        },
        "status": "configured" if (SENDGRID_API_KEY and SENDGRID_FROM_EMAIL) else "not_configured"
    }
    return config_status


@router.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """
    Get application performance metrics.
    
    Returns health status and performance statistics.
    """
    return get_health_metrics()


@api_router.post("/log-clicks")
@limiter.limit("1000/hour")
async def log_clicks_endpoint(
    request: Request,
    data: dict
) -> Dict[str, Any]:
    """Log user clicks for debugging purposes."""
    try:
        clicks = data.get('clicks', [])
        page = data.get('page', 'unknown')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # Log each click with detailed information
        logger.info("="*80)
        logger.info("CLICK TRACKING - BATCH RECEIVED")
        logger.info("="*80)
        logger.info(f"Page: {page}")
        logger.info(f"Batch timestamp: {timestamp}")
        logger.info(f"Number of clicks: {len(clicks)}")
        logger.info(f"Client IP: {request.client.host if request.client else 'unknown'}")
        logger.info(f"User Agent: {request.headers.get('user-agent', 'unknown')}")
        logger.info("")
        
        for i, click in enumerate(clicks, 1):
            element = click.get('element', {})
            page_info = click.get('page', {})
            user_info = click.get('user', {})
            viewport = click.get('viewport', {})
            event_info = click.get('event', {})
            
            logger.info(f"--- Click #{i} ---")
            logger.info(f"Timestamp: {click.get('timestamp', 'unknown')}")
            logger.info(f"Page URL: {page_info.get('url', 'unknown')}")
            logger.info(f"Page Title: {page_info.get('title', 'unknown')}")
            logger.info(f"User Logged In: {user_info.get('loggedIn', False)}")
            if user_info.get('email'):
                logger.info(f"User Email: {user_info.get('email')}")
            logger.info(f"Element Tag: {element.get('tag', 'unknown')}")
            if element.get('id'):
                logger.info(f"Element ID: {element.get('id')}")
            if element.get('className'):
                logger.info(f"Element Class: {element.get('className')}")
            if element.get('text'):
                logger.info(f"Element Text: {element.get('text')[:100]}")
            if element.get('href'):
                logger.info(f"Element Href: {element.get('href')}")
            if element.get('type'):
                logger.info(f"Element Type: {element.get('type')}")
            if element.get('name'):
                logger.info(f"Element Name: {element.get('name')}")
            if element.get('value'):
                logger.info(f"Element Value: {element.get('value')}")
            if element.get('dataset'):
                logger.info(f"Element Dataset: {element.get('dataset')}")
            if element.get('ariaLabel'):
                logger.info(f"Element Aria Label: {element.get('ariaLabel')}")
            if element.get('role'):
                logger.info(f"Element Role: {element.get('role')}")
            
            parent = click.get('parent')
            if parent:
                logger.info(f"Parent Tag: {parent.get('tag', 'unknown')}")
                if parent.get('id'):
                    logger.info(f"Parent ID: {parent.get('id')}")
                if parent.get('className'):
                    logger.info(f"Parent Class: {parent.get('className')}")
            
            logger.info(f"Viewport: {viewport.get('width')}x{viewport.get('height')}")
            logger.info(f"Scroll Position: ({viewport.get('scrollX', 0)}, {viewport.get('scrollY', 0)})")
            
            if event_info.get('ctrlKey') or event_info.get('shiftKey') or event_info.get('altKey') or event_info.get('metaKey'):
                modifiers = []
                if event_info.get('ctrlKey'): modifiers.append('Ctrl')
                if event_info.get('shiftKey'): modifiers.append('Shift')
                if event_info.get('altKey'): modifiers.append('Alt')
                if event_info.get('metaKey'): modifiers.append('Meta')
                logger.info(f"Modifiers: {', '.join(modifiers)}")
            
            logger.info("")
        
        logger.info("="*80)
        logger.info("CLICK TRACKING - BATCH COMPLETE")
        logger.info("="*80)
        
        return {"status": "logged", "clicks_received": len(clicks)}
    
    except Exception as e:
        logger.error(f"Error logging clicks: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

