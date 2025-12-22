"""
Advanced caching strategies with multi-level caching.

Provides L1 (in-memory) and L2 (Redis) caching with intelligent
cache invalidation and warming strategies.
"""

import logging
import json
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps

from app.core.cache import (
    _redis_client, REDIS_AVAILABLE, REDIS_URL,
    CACHE_EXPIRY_HOURS
)

logger = logging.getLogger(__name__)

# L1 Cache (in-memory, fastest)
_l1_cache: Dict[str, Dict[str, Any]] = {}
_l1_cache_timestamps: Dict[str, datetime] = {}

# L1 Cache size limit (prevent memory issues)
L1_CACHE_MAX_SIZE = 1000
L1_CACHE_EXPIRY_MINUTES = 5  # L1 cache expires faster


def _get_l1_cache_key(base_key: str) -> str:
    """Get L1 cache key."""
    return f"l1:{base_key}"


def _get_l2_cache_key(base_key: str) -> str:
    """Get L2 cache key."""
    return f"l2:{base_key}"


def get_from_cache(key: str) -> Optional[Dict[str, Any]]:
    """
    Get value from multi-level cache.
    
    Checks L1 (in-memory) first, then L2 (Redis), then returns None.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value or None
    """
    # Try L1 cache first (fastest)
    l1_key = _get_l1_cache_key(key)
    if l1_key in _l1_cache:
        timestamp = _l1_cache_timestamps.get(l1_key)
        if timestamp and datetime.now() - timestamp < timedelta(minutes=L1_CACHE_EXPIRY_MINUTES):
            logger.debug(f"L1 cache hit: {key}")
            return _l1_cache[l1_key]
        else:
            # L1 cache expired, remove it
            _l1_cache.pop(l1_key, None)
            _l1_cache_timestamps.pop(l1_key, None)
    
    # Try L2 cache (Redis)
    if REDIS_AVAILABLE and REDIS_URL and _redis_client:
        try:
            l2_key = _get_l2_cache_key(key)
            cached_data = _redis_client.get(l2_key)
            if cached_data:
                data = json.loads(cached_data)
                timestamp = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - timestamp < timedelta(hours=CACHE_EXPIRY_HOURS):
                    # Promote to L1 cache
                    _set_l1_cache(key, data)
                    logger.debug(f"L2 cache hit (promoted to L1): {key}")
                    return data
                else:
                    _redis_client.delete(l2_key)
        except Exception as e:
            logger.warning(f"L2 cache read error: {e}")
    
    logger.debug(f"Cache miss: {key}")
    return None


def set_in_cache(key: str, value: Dict[str, Any], expiry_hours: Optional[int] = None):
    """
    Set value in multi-level cache.
    
    Stores in both L1 (in-memory) and L2 (Redis) caches.
    
    Args:
        key: Cache key
        value: Value to cache
        expiry_hours: Optional expiry time (defaults to CACHE_EXPIRY_HOURS)
    """
    cache_data = {
        **value,
        "timestamp": datetime.now().isoformat()
    }
    
    # Store in L1 cache
    _set_l1_cache(key, cache_data)
    
    # Store in L2 cache (Redis)
    if REDIS_AVAILABLE and REDIS_URL and _redis_client:
        try:
            l2_key = _get_l2_cache_key(key)
            expiry = expiry_hours or CACHE_EXPIRY_HOURS
            _redis_client.setex(
                l2_key,
                timedelta(hours=expiry),
                json.dumps(cache_data)
            )
            logger.debug(f"Stored in L2 cache: {key}")
        except Exception as e:
            logger.warning(f"L2 cache write error: {e}")


def _set_l1_cache(key: str, value: Dict[str, Any]):
    """Set value in L1 cache with size management."""
    l1_key = _get_l1_cache_key(key)
    
    # Manage cache size (LRU eviction)
    if len(_l1_cache) >= L1_CACHE_MAX_SIZE:
        # Remove oldest entry
        if _l1_cache_timestamps:
            oldest_key = min(_l1_cache_timestamps.items(), key=lambda x: x[1])[0]
            _l1_cache.pop(oldest_key, None)
            _l1_cache_timestamps.pop(oldest_key, None)
    
    _l1_cache[l1_key] = value
    _l1_cache_timestamps[l1_key] = datetime.now()
    logger.debug(f"Stored in L1 cache: {key}")


def invalidate_cache(key: str):
    """
    Invalidate cache entry from both L1 and L2.
    
    Args:
        key: Cache key to invalidate
    """
    # Remove from L1
    l1_key = _get_l1_cache_key(key)
    _l1_cache.pop(l1_key, None)
    _l1_cache_timestamps.pop(l1_key, None)
    
    # Remove from L2
    if REDIS_AVAILABLE and REDIS_URL and _redis_client:
        try:
            l2_key = _get_l2_cache_key(key)
            _redis_client.delete(l2_key)
            logger.debug(f"Invalidated cache: {key}")
        except Exception as e:
            logger.warning(f"L2 cache invalidation error: {e}")


def invalidate_cache_pattern(pattern: str):
    """
    Invalidate all cache entries matching a pattern.
    
    Args:
        pattern: Pattern to match (e.g., "chart:*")
    """
    # L1 cache - simple pattern matching
    keys_to_remove = [
        k for k in _l1_cache.keys()
        if pattern.replace("*", "") in k
    ]
    for key in keys_to_remove:
        _l1_cache.pop(key, None)
        _l1_cache_timestamps.pop(key, None)
    
    # L2 cache - Redis pattern matching
    if REDIS_AVAILABLE and REDIS_URL and _redis_client:
        try:
            l2_pattern = _get_l2_cache_key(pattern)
            keys = _redis_client.keys(l2_pattern)
            if keys:
                _redis_client.delete(*keys)
                logger.debug(f"Invalidated {len(keys)} cache entries matching: {pattern}")
        except Exception as e:
            logger.warning(f"L2 cache pattern invalidation error: {e}")


def cache_warm(func: Optional[Callable] = None, keys: Optional[list] = None):
    """
    Decorator to warm cache with pre-computed values.
    
    Usage:
        @cache_warm(keys=["popular:chart:1", "popular:chart:2"])
        def warm_popular_charts():
            # Pre-compute and cache popular charts
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)
            if keys:
                for key in keys:
                    if isinstance(result, dict) and key in result:
                        set_in_cache(key, result[key])
            return result
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    stats = {
        "l1_cache": {
            "size": len(_l1_cache),
            "max_size": L1_CACHE_MAX_SIZE,
            "usage_percent": round((len(_l1_cache) / L1_CACHE_MAX_SIZE) * 100, 2)
        },
        "l2_cache": {
            "available": REDIS_AVAILABLE and REDIS_URL and _redis_client is not None,
            "type": "redis" if (REDIS_AVAILABLE and REDIS_URL and _redis_client) else "none"
        }
    }
    
    # Get Redis stats if available
    if REDIS_AVAILABLE and REDIS_URL and _redis_client:
        try:
            info = _redis_client.info("memory")
            stats["l2_cache"]["memory_used_mb"] = round(info.get("used_memory", 0) / 1024 / 1024, 2)
            stats["l2_cache"]["memory_peak_mb"] = round(info.get("used_memory_peak", 0) / 1024 / 1024, 2)
        except Exception as e:
            logger.warning(f"Error getting Redis stats: {e}")
    
    return stats

