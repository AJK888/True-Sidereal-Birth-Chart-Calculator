"""
Health check utilities.

Provides comprehensive health checks for dependencies and system status.
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def check_database_health() -> Dict[str, Any]:
    """
    Check database connection health.
    
    Returns:
        Dictionary with database health status
    """
    try:
        from database import SessionLocal, engine
        from sqlalchemy import text
        
        # Try to create a session and execute a simple query
        start_time = time.time()
        db = SessionLocal()
        try:
            # Simple query to test connection
            db.execute(text("SELECT 1"))
            db.commit()
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            # Check connection pool status
            pool = engine.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time, 2),
                "pool": pool_status,
                "error": None
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "response_time_ms": None,
            "pool": None,
            "error": str(e)
        }


def check_cache_health() -> Dict[str, Any]:
    """
    Check cache (Redis/in-memory) health.
    
    Returns:
        Dictionary with cache health status
    """
    try:
        from app.core.cache import _redis_client, REDIS_AVAILABLE, REDIS_URL
        
        if REDIS_AVAILABLE and REDIS_URL and _redis_client:
            # Test Redis connection
            start_time = time.time()
            _redis_client.ping()
            response_time = (time.time() - start_time) * 1000
            
            # Get Redis info
            try:
                info = _redis_client.info("server")
                redis_version = info.get("redis_version", "unknown")
            except:
                redis_version = "unknown"
            
            return {
                "status": "healthy",
                "type": "redis",
                "response_time_ms": round(response_time, 2),
                "redis_version": redis_version,
                "error": None
            }
        else:
            # In-memory cache (always available)
            return {
                "status": "healthy",
                "type": "in-memory",
                "response_time_ms": 0,
                "error": None
            }
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            "status": "unhealthy",
            "type": "unknown",
            "response_time_ms": None,
            "error": str(e)
        }


def check_ephemeris_health() -> Dict[str, Any]:
    """
    Check Swiss Ephemeris files availability.
    
    Returns:
        Dictionary with ephemeris health status
    """
    try:
        import swisseph as swe
        from app.config import SWEP_PATH, DEFAULT_SWISS_EPHEMERIS_PATH
        import os
        
        ephe_path = SWEP_PATH or DEFAULT_SWISS_EPHEMERIS_PATH
        
        if isinstance(ephe_path, str) and os.path.exists(ephe_path):
            # Check if we can access ephemeris
            try:
                # Try to calculate a simple position
                swe.set_ephe_path(ephe_path)
                jd = swe.julday(2025, 1, 1, 0.0)
                result = swe.calc_ut(jd, 0)  # Sun position
                
                if result[0] == 0:  # Success
                    return {
                        "status": "healthy",
                        "path": ephe_path,
                        "error": None
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "path": ephe_path,
                        "error": f"Ephemeris calculation failed with code {result[0]}"
                    }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "path": ephe_path,
                    "error": str(e)
                }
        else:
            return {
                "status": "unhealthy",
                "path": ephe_path,
                "error": "Ephemeris path does not exist"
            }
    except Exception as e:
        logger.error(f"Ephemeris health check failed: {e}")
        return {
            "status": "unhealthy",
            "path": None,
            "error": str(e)
        }


def get_comprehensive_health() -> Dict[str, Any]:
    """
    Get comprehensive health status for all dependencies.
    
    Returns:
        Dictionary with overall health and individual component statuses
    """
    checks = {
        "database": check_database_health(),
        "cache": check_cache_health(),
        "ephemeris": check_ephemeris_health(),
    }
    
    # Determine overall health
    all_healthy = all(
        check.get("status") == "healthy" 
        for check in checks.values()
    )
    
    any_unhealthy = any(
        check.get("status") == "unhealthy"
        for check in checks.values()
    )
    
    if all_healthy:
        overall_status = "healthy"
    elif any_unhealthy:
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks
    }


def get_readiness() -> Dict[str, Any]:
    """
    Get readiness status (can the service accept traffic?).
    
    Returns:
        Dictionary with readiness status
    """
    health = get_comprehensive_health()
    
    # Service is ready if database is healthy (critical dependency)
    database_healthy = health["checks"]["database"].get("status") == "healthy"
    
    return {
        "ready": database_healthy,
        "status": "ready" if database_healthy else "not_ready",
        "timestamp": datetime.now().isoformat(),
        "database": health["checks"]["database"]["status"]
    }


def get_liveness() -> Dict[str, Any]:
    """
    Get liveness status (is the service alive?).
    
    Returns:
        Dictionary with liveness status
    """
    # Service is alive if we can respond (this function running means it's alive)
    return {
        "alive": True,
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }

