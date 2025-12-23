"""
Developer Tools and Utilities

Development-only utilities for debugging, testing, and development workflows.
"""

import logging
import os
import sys
import traceback
from typing import Dict, Any, Optional, List
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)


def is_development() -> bool:
    """
    Check if running in development mode.
    
    Returns:
        True if in development mode, False otherwise
    """
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "production")).lower()
    return env in ["development", "dev", "local", "test"]


def is_production() -> bool:
    """
    Check if running in production mode.
    
    Returns:
        True if in production mode, False otherwise
    """
    return not is_development()


def dev_only(func):
    """
    Decorator to restrict function to development mode only.
    
    Raises:
        RuntimeError: If called in production mode
    
    Usage:
        @dev_only
        def debug_function():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_production():
            raise RuntimeError(
                f"Function '{func.__name__}' is only available in development mode"
            )
        return func(*args, **kwargs)
    
    return wrapper


def get_environment_info() -> Dict[str, Any]:
    """
    Get environment information for debugging.
    
    Returns:
        Dictionary with environment details
    """
    return {
        "environment": os.getenv("ENVIRONMENT", os.getenv("ENV", "unknown")),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "working_directory": os.getcwd(),
        "pid": os.getpid(),
        "platform": sys.platform,
        "is_development": is_development(),
        "is_production": is_production()
    }


def get_import_info() -> Dict[str, Any]:
    """
    Get information about imported modules.
    
    Returns:
        Dictionary with import information
    """
    import_info = {
        "loaded_modules": len(sys.modules),
        "module_names": sorted(list(sys.modules.keys()))[:50]  # First 50
    }
    
    # Check for key dependencies
    key_modules = [
        "fastapi", "sqlalchemy", "redis", "requests", "pendulum",
        "swisseph", "pydantic", "slowapi"
    ]
    
    module_status = {}
    for module_name in key_modules:
        try:
            module = __import__(module_name)
            module_status[module_name] = {
                "loaded": True,
                "version": getattr(module, "__version__", "unknown")
            }
        except ImportError:
            module_status[module_name] = {
                "loaded": False,
                "version": None
            }
    
    import_info["key_modules"] = module_status
    return import_info


def format_exception(e: Exception, include_traceback: bool = True) -> Dict[str, Any]:
    """
    Format exception for better debugging.
    
    Args:
        e: Exception to format
        include_traceback: Whether to include traceback
    
    Returns:
        Dictionary with formatted exception information
    """
    result = {
        "type": type(e).__name__,
        "message": str(e),
        "module": getattr(e, "__module__", "unknown")
    }
    
    if include_traceback:
        result["traceback"] = traceback.format_exc()
        result["stack"] = traceback.format_tb(e.__traceback__)
    
    return result


def log_request_details(request, include_body: bool = False) -> Dict[str, Any]:
    """
    Log detailed request information for debugging.
    
    Args:
        request: FastAPI Request object
        include_body: Whether to include request body
    
    Returns:
        Dictionary with request details
    """
    details = {
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client": {
            "host": request.client.host if request.client else None,
            "port": request.client.port if request.client else None
        }
    }
    
    if include_body:
        try:
            # Note: This will consume the request body
            # Only use in development
            if hasattr(request, "_body"):
                details["body"] = request._body.decode() if isinstance(request._body, bytes) else request._body
        except Exception as e:
            details["body_error"] = str(e)
    
    return details


def create_test_fixture(name: str, data: Dict[str, Any]) -> str:
    """
    Create a test fixture file from data.
    
    Args:
        name: Fixture name
        data: Data to save
    
    Returns:
        Path to created fixture file
    """
    import json
    from pathlib import Path
    
    fixtures_dir = Path("tests/fixtures")
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    fixture_path = fixtures_dir / f"{name}.json"
    
    with open(fixture_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info(f"Created test fixture: {fixture_path}")
    return str(fixture_path)


def load_test_fixture(name: str) -> Dict[str, Any]:
    """
    Load a test fixture file.
    
    Args:
        name: Fixture name
    
    Returns:
        Fixture data
    """
    import json
    from pathlib import Path
    
    fixture_path = Path("tests/fixtures") / f"{name}.json"
    
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    
    with open(fixture_path, "r") as f:
        return json.load(f)


def get_database_info(db_session) -> Dict[str, Any]:
    """
    Get database connection information.
    
    Args:
        db_session: SQLAlchemy session
    
    Returns:
        Dictionary with database information
    """
    try:
        engine = db_session.bind
        info = {
            "driver": engine.driver,
            "url": str(engine.url).replace(engine.url.password or "", "***") if engine.url.password else str(engine.url),
            "pool_size": engine.pool.size() if hasattr(engine.pool, "size") else None,
            "checked_out": engine.pool.checkedout() if hasattr(engine.pool, "checkedout") else None,
            "checked_in": engine.pool.checkedin() if hasattr(engine.pool, "checkedin") else None
        }
        
        # Try to get database version
        try:
            result = db_session.execute("SELECT version()")
            version = result.scalar()
            info["version"] = version
        except Exception:
            pass
        
        return info
    except Exception as e:
        return {
            "error": str(e),
            "type": type(e).__name__
        }


def get_cache_info() -> Dict[str, Any]:
    """
    Get cache connection information.
    
    Returns:
        Dictionary with cache information
    """
    try:
        from app.core.advanced_cache import redis_client
        
        if redis_client:
            try:
                info = redis_client.info()
                return {
                    "connected": True,
                    "redis_version": info.get("redis_version"),
                    "used_memory_human": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                    "keyspace": info.get("db0", {})
                }
            except Exception as e:
                return {
                    "connected": False,
                    "error": str(e)
                }
        else:
            return {
                "connected": False,
                "mode": "in_memory_only"
            }
    except ImportError:
        return {
            "connected": False,
            "error": "Redis not available"
        }


def validate_config() -> Dict[str, Any]:
    """
    Validate application configuration.
    
    Returns:
        Dictionary with validation results
    """
    from app.config import (
        DATABASE_URL, SECRET_KEY, OPENCAGE_KEY, SENDGRID_API_KEY,
        ADMIN_EMAIL, ADMIN_SECRET_KEY
    )
    
    validation = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    # Required config
    required = {
        "DATABASE_URL": DATABASE_URL,
        "SECRET_KEY": SECRET_KEY
    }
    
    for key, value in required.items():
        validation["checks"][key] = {
            "required": True,
            "present": value is not None and value != "",
            "value_length": len(value) if value else 0
        }
    
    # Optional config
    optional = {
        "OPENCAGE_KEY": OPENCAGE_KEY,
        "SENDGRID_API_KEY": SENDGRID_API_KEY,
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "ADMIN_SECRET_KEY": ADMIN_SECRET_KEY
    }
    
    for key, value in optional.items():
        validation["checks"][key] = {
            "required": False,
            "present": value is not None and value != "",
            "value_length": len(value) if value else 0
        }
    
    # Overall status
    all_required_present = all(
        check["present"]
        for check in validation["checks"].values()
        if check.get("required", False)
    )
    
    validation["status"] = "valid" if all_required_present else "invalid"
    validation["missing_required"] = [
        key for key, check in validation["checks"].items()
        if check.get("required", False) and not check["present"]
    ]
    
    return validation

