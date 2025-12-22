"""
Advanced rate limiting with tiered limits.

Provides subscription-based rate limiting tiers and usage tracking.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Request

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Rate limit tiers
RATE_LIMIT_TIERS = {
    "free": {
        "chart_calculations": "50/day",
        "readings": "10/day",
        "famous_people": "20/day",
        "synastry": "5/day"
    },
    "basic": {
        "chart_calculations": "200/day",
        "readings": "50/day",
        "famous_people": "100/day",
        "synastry": "20/day"
    },
    "premium": {
        "chart_calculations": "1000/day",
        "readings": "500/day",
        "famous_people": "500/day",
        "synastry": "100/day"
    },
    "unlimited": {
        "chart_calculations": "10000/day",
        "readings": "10000/day",
        "famous_people": "10000/day",
        "synastry": "10000/day"
    }
}


def get_user_tier(user_id: Optional[int] = None, db=None) -> str:
    """
    Get user's rate limit tier based on subscription.
    
    Args:
        user_id: User ID (optional)
        db: Database session (optional)
        
    Returns:
        Tier name: "free", "basic", "premium", or "unlimited"
    """
    if not user_id or not db:
        return "free"
    
    try:
        from database import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return "free"
        
        # Check subscription status
        from subscription import has_active_subscription
        if has_active_subscription(user, db):
            # Check subscription type
            if user.stripe_subscription_id:
                # Premium subscription
                return "premium"
            else:
                # Basic subscription
                return "basic"
        else:
            return "free"
    except Exception as e:
        logger.warning(f"Error getting user tier: {e}")
        return "free"


def get_rate_limit_for_tier(tier: str, endpoint_type: str) -> str:
    """
    Get rate limit string for a tier and endpoint type.
    
    Args:
        tier: Tier name ("free", "basic", "premium", "unlimited")
        endpoint_type: Endpoint type ("chart_calculations", "readings", etc.)
        
    Returns:
        Rate limit string (e.g., "200/day")
    """
    tier_limits = RATE_LIMIT_TIERS.get(tier, RATE_LIMIT_TIERS["free"])
    return tier_limits.get(endpoint_type, "50/day")


def get_rate_limit_key_with_tier(request: Request) -> str:
    """
    Get rate limit key that includes tier information.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limit key string
    """
    # Try to get user ID from request state
    user_id = getattr(request.state, "user_id", None)
    
    if user_id:
        # Get user tier
        db = getattr(request.state, "db", None)
        tier = get_user_tier(user_id, db)
        return f"user:{user_id}:tier:{tier}"
    
    # Fall back to IP address for anonymous users
    return f"ip:{get_remote_address(request)}:tier:free"


def get_rate_limit_for_endpoint(
    request: Request,
    endpoint_type: str,
    default_limit: str = "50/day"
) -> str:
    """
    Get rate limit for an endpoint based on user tier.
    
    Args:
        request: FastAPI request object
        endpoint_type: Endpoint type ("chart_calculations", "readings", etc.)
        default_limit: Default limit if tier not found
        
    Returns:
        Rate limit string (e.g., "200/day")
    """
    user_id = getattr(request.state, "user_id", None)
    db = getattr(request.state, "db", None)
    
    if user_id and db:
        tier = get_user_tier(user_id, db)
        return get_rate_limit_for_tier(tier, endpoint_type)
    
    # Anonymous users get free tier limits
    return get_rate_limit_for_tier("free", endpoint_type)


def track_rate_limit_usage(
    key: str,
    endpoint_type: str,
    redis_client=None
) -> Dict[str, Any]:
    """
    Track rate limit usage for analytics.
    
    Args:
        key: Rate limit key
        endpoint_type: Endpoint type
        redis_client: Redis client (optional)
        
    Returns:
        Usage statistics
    """
    # This would integrate with analytics system
    # For now, just return basic info
    return {
        "key": key,
        "endpoint_type": endpoint_type,
        "timestamp": datetime.now().isoformat()
    }


def get_rate_limit_headers(
    remaining: int,
    reset_time: datetime,
    limit: int
) -> Dict[str, str]:
    """
    Get rate limit headers for response.
    
    Args:
        remaining: Remaining requests
        reset_time: When rate limit resets
        limit: Total limit
        
    Returns:
        Dictionary of headers
    """
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(int(reset_time.timestamp()))
    }

