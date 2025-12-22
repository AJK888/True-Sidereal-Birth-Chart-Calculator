"""
Shared dependencies for API routes.

This module provides shared dependencies like rate limiters, database sessions, etc.
"""

from slowapi.util import get_remote_address
from fastapi import Request

# Rate limiter key function
# Note: This is a simplified version - the actual implementation in api.py includes
# FRIENDS_AND_FAMILY_KEY bypass logic. The limiter instance is created in api.py
# and shared via app.state.limiter. Routers can access it through the app instance.
def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key for a request.
    Uses IP address for anonymous users, user ID for authenticated users.
    """
    # Try to get user from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    
    return get_remote_address(request)


# Limiter instance will be created in api.py and made available to routers
# Routers should use: from fastapi import Request; limiter = Request.app.state.limiter
# Or better: import the limiter after app creation in api.py

