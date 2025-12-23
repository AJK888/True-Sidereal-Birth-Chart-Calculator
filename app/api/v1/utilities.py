"""
Utilities API Routes

Health check, ping, diagnostic endpoints, and utility functions.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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
from app.utils.health import (
    get_comprehensive_health,
    get_readiness,
    get_liveness,
    check_database_health,
    check_cache_health
)


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


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics."""
    try:
        from app.core.cache_analytics import get_cache_statistics
        stats = get_cache_statistics()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/cache/recommendations")
async def get_cache_recommendations() -> Dict[str, Any]:
    """Get cache optimization recommendations."""
    try:
        from app.core.cache_analytics import get_cache_recommendations
        recommendations = get_cache_recommendations()
        return {
            "status": "success",
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Failed to get cache recommendations: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/cache/warm")
async def warm_cache(request: Request) -> Dict[str, Any]:
    """Manually trigger cache warming."""
    try:
        from app.utils.cache_warming import cache_warmer
        from app.core.exceptions import AuthorizationError
        from auth import get_current_user
        from database import get_db
        
        # Check if user is admin
        db = next(get_db())
        try:
            current_user = get_current_user(request, db)
            if not current_user or not current_user.is_admin:
                raise AuthorizationError("Admin access required")
        finally:
            db.close()
        
        # Get strategy names from request (optional)
        body = await request.json() if request.method == "POST" else {}
        strategy_names = body.get("strategies", [])
        
        if strategy_names:
            results = await cache_warmer.warm_selective(strategy_names)
        else:
            results = await cache_warmer.warm_all()
        
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        logger.error(f"Cache warming failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/performance/stats")
async def get_performance_stats() -> Dict[str, Any]:
    """Get performance profiling statistics."""
    try:
        from app.utils.performance_profiler import get_performance_statistics
        stats = get_performance_statistics()
        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get performance stats: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/performance/slow")
async def get_slow_operations(limit: int = 20) -> Dict[str, Any]:
    """Get slowest operations."""
    try:
        from app.utils.performance_profiler import get_slow_operations
        slow_ops = get_slow_operations(limit=limit)
        return {
            "status": "success",
            "operations": slow_ops
        }
    except Exception as e:
        logger.error(f"Failed to get slow operations: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/performance/function/{function_name:path}")
async def get_function_stats(function_name: str) -> Dict[str, Any]:
    """Get statistics for a specific function."""
    try:
        from app.utils.performance_profiler import get_function_statistics
        stats = get_function_statistics(function_name)
        if stats:
            return {
                "status": "success",
                "stats": stats
            }
        else:
            return {
                "status": "not_found",
                "message": f"Function '{function_name}' not found"
            }
    except Exception as e:
        logger.error(f"Failed to get function stats: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/performance/resources")
async def get_resource_usage() -> Dict[str, Any]:
    """Get current resource usage statistics."""
    try:
        from app.utils.performance_profiler import get_resource_usage
        usage = get_resource_usage()
        return {
            "status": "success",
            "resources": usage
        }
    except Exception as e:
        logger.error(f"Failed to get resource usage: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/performance/recommendations")
async def get_performance_recommendations() -> Dict[str, Any]:
    """Get performance optimization recommendations."""
    try:
        from app.utils.performance_profiler import get_performance_recommendations
        recommendations = get_performance_recommendations()
        return {
            "status": "success",
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/performance/profiler/start")
async def start_profiler(request: Request, name: str) -> Dict[str, Any]:
    """Start a profiler for a specific operation (admin only)."""
    try:
        from app.utils.performance_profiler import start_profiler
        from app.core.exceptions import AuthorizationError
        from auth import get_current_user
        from database import get_db
        
        # Check if user is admin
        db = next(get_db())
        try:
            current_user = get_current_user(request, db)
            if not current_user or not current_user.is_admin:
                raise AuthorizationError("Admin access required")
        finally:
            db.close()
        
        profiler_id = start_profiler(name)
        return {
            "status": "success",
            "profiler_id": profiler_id
        }
    except Exception as e:
        logger.error(f"Failed to start profiler: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/performance/profiler/stop")
async def stop_profiler(request: Request, profiler_id: str) -> Dict[str, Any]:
    """Stop a profiler and get results (admin only)."""
    try:
        from app.utils.performance_profiler import stop_profiler
        from app.core.exceptions import AuthorizationError
        from auth import get_current_user
        from database import get_db
        
        # Check if user is admin
        db = next(get_db())
        try:
            current_user = get_current_user(request, db)
            if not current_user or not current_user.is_admin:
                raise AuthorizationError("Admin access required")
        finally:
            db.close()
        
        results = stop_profiler(profiler_id)
        if results:
            return {
                "status": "success",
                "results": results
            }
        else:
            return {
                "status": "not_found",
                "message": f"Profiler '{profiler_id}' not found"
            }
    except Exception as e:
        logger.error(f"Failed to stop profiler: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """Get all circuit breaker statistics."""
    try:
        from app.core.circuit_breaker import get_all_circuit_breakers
        breakers = get_all_circuit_breakers()
        stats = {name: cb.get_stats() for name, cb in breakers.items()}
        return {
            "status": "success",
            "circuit_breakers": stats
        }
    except Exception as e:
        logger.error(f"Failed to get circuit breakers: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker_endpoint(request: Request, name: str) -> Dict[str, Any]:
    """Reset a circuit breaker (admin only)."""
    try:
        from app.core.circuit_breaker import reset_circuit_breaker
        from app.core.exceptions import AuthorizationError
        from auth import get_current_user
        from database import get_db
        
        # Check if user is admin
        db = next(get_db())
        try:
            current_user = get_current_user(request, db)
            if not current_user or not current_user.is_admin:
                raise AuthorizationError("Admin access required")
        finally:
            db.close()
        
        reset_circuit_breaker(name)
        return {
            "status": "success",
            "message": f"Circuit breaker '{name}' reset"
        }
    except ValueError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """
    Get application performance metrics.
    
    Returns health status and performance statistics.
    """
    return get_health_metrics()


@router.get("/version")
def get_api_version_info() -> Dict[str, Any]:
    """
    Get API version information.
    
    Returns current API version, supported versions, and deprecation info.
    """
    try:
        from app.core.api_versioning import get_version_info
        return {
            "status": "success",
            "version": get_version_info()
        }
    except Exception as e:
        logger.error(f"Failed to get version info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/languages")
def get_supported_languages_endpoint() -> Dict[str, Any]:
    """
    Get supported languages.
    
    Returns list of supported languages with codes and names.
    """
    try:
        from app.core.i18n import get_supported_languages
        return {
            "status": "success",
            **get_supported_languages()
        }
    except Exception as e:
        logger.error(f"Failed to get languages: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/content/{key:path}")
def get_localized_content_endpoint(
    request: Request,
    key: str,
    language: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get localized content by key.
    
    Args:
        key: Content key
        language: Optional language code (defaults to Accept-Language header or English)
    
    Returns:
        Localized content
    """
    try:
        from app.core.i18n import detect_language, get_translation
        from app.services.localization import get_localized_content
        
        # Detect language if not provided
        if not language:
            language = detect_language(dict(request.headers))
        
        content = get_localized_content(key, language)
        
        return {
            "status": "success",
            "key": key,
            "language": language,
            "content": content
        }
    except Exception as e:
        logger.error(f"Failed to get content: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check endpoint.
    
    Checks all dependencies (database, cache, ephemeris) and returns
    overall health status. Use for monitoring and alerting.
    """
    return get_comprehensive_health()


@router.get("/health/ready")
def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe endpoint.
    
    Returns whether the service is ready to accept traffic.
    Kubernetes/container orchestrators use this to determine if traffic
    should be routed to this instance.
    """
    return get_readiness()


@router.get("/health/live")
def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe endpoint.
    
    Returns whether the service is alive. Kubernetes/container orchestrators
    use this to determine if the container should be restarted.
    """
    return get_liveness()


# Development-only endpoints
@router.get("/dev/environment")
async def get_environment_info() -> Dict[str, Any]:
    """Get environment information (development only)."""
    try:
        from app.utils.dev_tools import get_environment_info, is_development
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        return {
            "status": "success",
            "environment": get_environment_info()
        }
    except Exception as e:
        logger.error(f"Failed to get environment info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/dev/imports")
async def get_import_info() -> Dict[str, Any]:
    """Get import information (development only)."""
    try:
        from app.utils.dev_tools import get_import_info, is_development
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        return {
            "status": "success",
            "imports": get_import_info()
        }
    except Exception as e:
        logger.error(f"Failed to get import info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/dev/database")
async def get_database_info(request: Request) -> Dict[str, Any]:
    """Get database connection information (development only)."""
    try:
        from app.utils.dev_tools import get_database_info, is_development
        from database import get_db
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        db = next(get_db())
        try:
            db_info = get_database_info(db)
            return {
                "status": "success",
                "database": db_info
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to get database info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/dev/cache")
async def get_cache_info() -> Dict[str, Any]:
    """Get cache connection information (development only)."""
    try:
        from app.utils.dev_tools import get_cache_info, is_development
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        cache_info = get_cache_info()
        return {
            "status": "success",
            "cache": cache_info
        }
    except Exception as e:
        logger.error(f"Failed to get cache info: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/dev/config")
async def validate_config_endpoint() -> Dict[str, Any]:
    """Validate application configuration (development only)."""
    try:
        from app.utils.dev_tools import validate_config, is_development
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        validation = validate_config()
        return {
            "status": "success",
            "validation": validation
        }
    except Exception as e:
        logger.error(f"Failed to validate config: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/dev/test-fixture/{name}")
async def create_test_fixture_endpoint(request: Request, name: str) -> Dict[str, Any]:
    """Create a test fixture from request data (development only)."""
    try:
        from app.utils.dev_tools import create_test_fixture, is_development
        import json
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        body = await request.json()
        fixture_path = create_test_fixture(name, body)
        
        return {
            "status": "success",
            "message": f"Fixture created: {fixture_path}",
            "path": fixture_path
        }
    except Exception as e:
        logger.error(f"Failed to create test fixture: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/dev/test-fixture/{name}")
async def load_test_fixture_endpoint(name: str) -> Dict[str, Any]:
    """Load a test fixture (development only)."""
    try:
        from app.utils.dev_tools import load_test_fixture, is_development
        
        if not is_development():
            return {
                "status": "error",
                "message": "This endpoint is only available in development mode"
            }
        
        fixture_data = load_test_fixture(name)
        return {
            "status": "success",
            "fixture": fixture_data
        }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Failed to load test fixture: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


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

