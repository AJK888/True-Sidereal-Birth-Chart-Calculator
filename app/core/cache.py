"""
Shared cache for the application.

Provides caching layer with Redis support (optional) and in-memory fallback.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Try to import Redis (optional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# Cache configuration
CACHE_EXPIRY_HOURS = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))  # Default 24 hours
REDIS_URL = os.getenv("REDIS_URL")  # Optional Redis URL

# Initialize Redis client if available
_redis_client: Optional[Any] = None
if REDIS_AVAILABLE and REDIS_URL:
    try:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()  # Test connection
        logger.info("Redis cache initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
        _redis_client = None

# In-memory cache fallback
_reading_cache: Dict[str, Dict[str, Any]] = {}


def get_reading_from_cache(chart_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a reading from cache (Redis or in-memory).
    
    Args:
        chart_hash: The chart hash key
        
    Returns:
        Cached reading data or None if not found/expired
    """
    # Try Redis first
    if _redis_client:
        try:
            cached_data = _redis_client.get(f"reading:{chart_hash}")
            if cached_data:
                data = json.loads(cached_data)
                # Check expiry
                timestamp = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - timestamp < timedelta(hours=CACHE_EXPIRY_HOURS):
                    return data
                else:
                    # Expired, remove it
                    _redis_client.delete(f"reading:{chart_hash}")
            return None
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}. Falling back to in-memory cache.")
    
    # Fallback to in-memory cache
    now = datetime.now()
    if chart_hash in _reading_cache:
        cached_data = _reading_cache[chart_hash]
        if now - cached_data['timestamp'] < timedelta(hours=CACHE_EXPIRY_HOURS):
            return cached_data
        else:
            del _reading_cache[chart_hash]
    return None


def set_reading_in_cache(chart_hash: str, reading: str, chart_name: str):
    """
    Store a reading in cache (Redis or in-memory).
    
    Args:
        chart_hash: The chart hash key
        reading: The reading text
        chart_name: The chart name
    """
    cache_data = {
        'reading': reading,
        'timestamp': datetime.now().isoformat(),
        'chart_name': chart_name
    }
    
    # Try Redis first
    if _redis_client:
        try:
            _redis_client.setex(
                f"reading:{chart_hash}",
                timedelta(hours=CACHE_EXPIRY_HOURS),
                json.dumps(cache_data)
            )
            return
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}. Falling back to in-memory cache.")
    
    # Fallback to in-memory cache
    _reading_cache[chart_hash] = {
        'reading': reading,
        'timestamp': datetime.now(),
        'chart_name': chart_name
    }


def clear_expired_cache():
    """Clear expired entries from in-memory cache."""
    now = datetime.now()
    expired_keys = [
        key for key, value in _reading_cache.items()
        if now - value['timestamp'] > timedelta(hours=CACHE_EXPIRY_HOURS)
    ]
    for key in expired_keys:
        del _reading_cache[key]
    
    if expired_keys:
        logger.info(f"Cleared {len(expired_keys)} expired cache entries")


# Backward compatibility - export reading_cache for existing code
reading_cache = _reading_cache
