"""
API Versioning Utilities

Provides utilities for API versioning and backward compatibility.
"""

import logging
from typing import Optional, Dict, Any, Callable
from fastapi import Request, HTTPException
from enum import Enum

logger = logging.getLogger(__name__)


class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"  # Future version


DEFAULT_VERSION = APIVersion.V1
CURRENT_VERSION = APIVersion.V1


def get_api_version(request: Request) -> APIVersion:
    """
    Extract API version from request.
    
    Checks:
    1. URL path (e.g., /api/v1/...)
    2. Header (X-API-Version)
    3. Query parameter (api_version)
    
    Args:
        request: FastAPI request object
    
    Returns:
        API version enum
    """
    # Check URL path
    path = request.url.path
    if "/api/v2/" in path:
        return APIVersion.V2
    elif "/api/v1/" in path:
        return APIVersion.V1
    
    # Check header
    version_header = request.headers.get("X-API-Version")
    if version_header:
        try:
            return APIVersion(version_header.lower())
        except ValueError:
            pass
    
    # Check query parameter
    version_param = request.query_params.get("api_version")
    if version_param:
        try:
            return APIVersion(version_param.lower())
        except ValueError:
            pass
    
    # Default to current version
    return DEFAULT_VERSION


def require_version(*allowed_versions: APIVersion):
    """
    Decorator to require specific API versions for an endpoint.
    
    Args:
        *allowed_versions: Allowed API versions
    
    Usage:
        @require_version(APIVersion.V1, APIVersion.V2)
        async def my_endpoint(request: Request):
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Find Request object in args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                request = kwargs.get("request")
            
            if request:
                version = get_api_version(request)
                if version not in allowed_versions:
                    raise HTTPException(
                        status_code=400,
                        detail=f"API version {version.value} not supported for this endpoint. "
                               f"Supported versions: {[v.value for v in allowed_versions]}"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def get_version_info() -> Dict[str, Any]:
    """
    Get API version information.
    
    Returns:
        Dictionary with version information
    """
    return {
        "current_version": CURRENT_VERSION.value,
        "default_version": DEFAULT_VERSION.value,
        "supported_versions": [v.value for v in APIVersion],
        "deprecation_info": {
            # Future: Add deprecation dates for old versions
        }
    }


def format_versioned_response(
    data: Any,
    version: APIVersion,
    request: Optional[Request] = None
) -> Dict[str, Any]:
    """
    Format response based on API version.
    
    Args:
        data: Response data
        version: API version
        request: Optional request object
    
    Returns:
        Versioned response dictionary
    """
    response = {
        "status": "success",
        "data": data,
        "api_version": version.value
    }
    
    # Add version-specific formatting
    if version == APIVersion.V2:
        # Future: V2 might have different response structure
        pass
    
    return response

