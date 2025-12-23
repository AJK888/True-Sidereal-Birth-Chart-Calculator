"""
Enhanced Health Checks

Comprehensive health check system for the application.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db, engine
from app.core.logging_config import setup_logger
from app.core.cache import _redis_client

logger = setup_logger(__name__)


class HealthChecker:
    """Health check utilities."""
    
    @staticmethod
    def check_database(db: Session) -> Dict[str, Any]:
        """Check database connectivity and health."""
        try:
            # Simple query to test connection
            db.execute(text("SELECT 1"))
            
            # Check connection pool
            pool = engine.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid()
            }
            
            return {
                "status": "healthy",
                "connected": True,
                "pool": pool_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def check_redis() -> Dict[str, Any]:
        """Check Redis connectivity and health."""
        if not _redis_client:
            return {
                "status": "not_configured",
                "connected": False,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        try:
            # Test connection
            _redis_client.ping()
            
            # Get info
            info = _redis_client.info()
            
            return {
                "status": "healthy",
                "connected": True,
                "version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    @staticmethod
    def check_dependencies() -> Dict[str, Any]:
        """Check external dependencies."""
        dependencies = {}
        
        # Check database
        db = next(get_db())
        try:
            dependencies["database"] = HealthChecker.check_database(db)
        finally:
            db.close()
        
        # Check Redis
        dependencies["redis"] = HealthChecker.check_redis()
        
        return dependencies
    
    @staticmethod
    def get_health_status(db: Session) -> Dict[str, Any]:
        """Get comprehensive health status."""
        # Check all components
        database_health = HealthChecker.check_database(db)
        redis_health = HealthChecker.check_redis()
        
        # Determine overall status
        overall_status = "healthy"
        if database_health["status"] != "healthy":
            overall_status = "unhealthy"
        elif redis_health["status"] == "unhealthy":
            overall_status = "degraded"  # Redis is optional
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": database_health,
                "redis": redis_health
            },
            "uptime": "N/A"  # Would need to track startup time
        }
    
    @staticmethod
    def get_readiness() -> Dict[str, Any]:
        """Check if application is ready to serve traffic."""
        db = next(get_db())
        try:
            database_health = HealthChecker.check_database(db)
            ready = database_health["status"] == "healthy"
            
            return {
                "ready": ready,
                "database": database_health["status"] == "healthy",
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            db.close()
    
    @staticmethod
    def get_liveness() -> Dict[str, Any]:
        """Check if application is alive."""
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat()
        }

