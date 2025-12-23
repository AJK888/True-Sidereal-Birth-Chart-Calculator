"""
Read Replica Support

Provides routing for read queries to read replicas when available.
"""

import os
import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Read replica URL (optional)
READ_REPLICA_URL = os.getenv("READ_REPLICA_URL")

# Read replica engine (created if READ_REPLICA_URL is set)
_read_replica_engine = None
_read_replica_session = None

if READ_REPLICA_URL:
    try:
        _read_replica_engine = create_engine(
            READ_REPLICA_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        _read_replica_session = sessionmaker(bind=_read_replica_engine)
        logger.info("Read replica connection configured")
    except Exception as e:
        logger.warning(f"Failed to configure read replica: {e}")


def get_read_session() -> Optional[Session]:
    """
    Get a database session for read operations.
    
    Uses read replica if available, otherwise returns None (use regular session).
    
    Returns:
        Database session for reads, or None if read replica not configured
    """
    if _read_replica_session:
        return _read_replica_session()
    return None


def use_read_replica(func):
    """
    Decorator to route read queries to read replica.
    
    Usage:
        @use_read_replica
        def get_user_charts(user_id):
            db = get_read_session() or get_db()
            return db.query(SavedChart).filter(...).all()
    """
    def wrapper(*args, **kwargs):
        # Check if function uses 'db' parameter
        import inspect
        sig = inspect.signature(func)
        
        # If db parameter exists and read replica available, use it
        if 'db' in sig.parameters and _read_replica_session:
            # Replace db with read replica session
            kwargs['db'] = get_read_session() or kwargs.get('db')
        
        return func(*args, **kwargs)
    
    return wrapper


def is_read_replica_available() -> bool:
    """
    Check if read replica is available.
    
    Returns:
        True if read replica is configured and available
    """
    return _read_replica_engine is not None


def get_replica_health() -> dict:
    """
    Get read replica health status.
    
    Returns:
        Dictionary with replica health information
    """
    if not _read_replica_engine:
        return {
            "available": False,
            "configured": False
        }
    
    try:
        # Test connection
        with _read_replica_engine.connect() as conn:
            conn.execute("SELECT 1")
        
        return {
            "available": True,
            "configured": True,
            "status": "healthy"
        }
    except Exception as e:
        return {
            "available": False,
            "configured": True,
            "status": "unhealthy",
            "error": str(e)
        }

