"""
Cache Enhancements

Advanced caching utilities with TTL management, cache invalidation, and statistics.
"""

import logging
import json
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
from functools import wraps

from app.core.cache import _redis_client, _reading_cache, _famous_people_cache
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


# Cache statistics
cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
    "errors": 0
}


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate a cache key from prefix and arguments."""
    # Create a hash of the arguments
    key_parts = [prefix]
    if args:
        key_parts.extend(str(arg) for arg in args)
    if kwargs:
        sorted_kwargs = sorted(kwargs.items())
        key_parts.extend(f"{k}:{v}" for k, v in sorted_kwargs)
    
    key_string = ":".join(key_parts)
    # Create hash for long keys
    if len(key_string) > 200:
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"
    return key_string


def cache_result(
    ttl_seconds: int = 3600,
    key_prefix: str = "cache",
    use_redis: bool = True
):
    """
    Decorator to cache function results.
    
    Args:
        ttl_seconds: Time to live in seconds
        key_prefix: Prefix for cache key
        use_redis: Whether to use Redis (if available)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = get_cache_key(key_prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = get_cached_value(cache_key, use_redis=use_redis)
            if cached_value is not None:
                cache_stats["hits"] += 1
                return cached_value
            
            # Cache miss - execute function
            cache_stats["misses"] += 1
            result = func(*args, **kwargs)
            
            # Store in cache
            set_cached_value(cache_key, result, ttl_seconds, use_redis=use_redis)
            
            return result
        return wrapper
    return decorator


def get_cached_value(
    key: str,
    use_redis: bool = True
) -> Optional[Any]:
    """Get a value from cache."""
    # Try Redis first
    if use_redis and _redis_client:
        try:
            cached_data = _redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")
            cache_stats["errors"] += 1
    
    # Fallback to in-memory cache
    if key in _reading_cache:
        return _reading_cache[key].get("value")
    
    return None


def set_cached_value(
    key: str,
    value: Any,
    ttl_seconds: int = 3600,
    use_redis: bool = True
):
    """Set a value in cache."""
    cache_stats["sets"] += 1
    
    # Try Redis first
    if use_redis and _redis_client:
        try:
            _redis_client.setex(
                key,
                ttl_seconds,
                json.dumps(value, default=str)
            )
            return
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")
            cache_stats["errors"] += 1
    
    # Fallback to in-memory cache
    _reading_cache[key] = {
        "value": value,
        "timestamp": datetime.now(),
        "ttl": ttl_seconds
    }


def delete_cached_value(key: str, use_redis: bool = True):
    """Delete a value from cache."""
    cache_stats["deletes"] += 1
    
    # Try Redis first
    if use_redis and _redis_client:
        try:
            _redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Redis cache delete error: {e}")
            cache_stats["errors"] += 1
    
    # Remove from in-memory cache
    if key in _reading_cache:
        del _reading_cache[key]


def invalidate_cache_pattern(pattern: str, use_redis: bool = True):
    """Invalidate all cache keys matching a pattern."""
    deleted_count = 0
    
    # Try Redis first
    if use_redis and _redis_client:
        try:
            keys = _redis_client.keys(pattern)
            if keys:
                _redis_client.delete(*keys)
                deleted_count = len(keys)
        except Exception as e:
            logger.warning(f"Redis cache pattern delete error: {e}")
    
    # Remove from in-memory cache
    keys_to_delete = [k for k in _reading_cache.keys() if pattern in k]
    for key in keys_to_delete:
        del _reading_cache[key]
        deleted_count += 1
    
    cache_stats["deletes"] += deleted_count
    return deleted_count


def get_cache_statistics() -> Dict[str, Any]:
    """Get cache performance statistics."""
    total_requests = cache_stats["hits"] + cache_stats["misses"]
    hit_rate = (cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
    
    return {
        "hits": cache_stats["hits"],
        "misses": cache_stats["misses"],
        "sets": cache_stats["sets"],
        "deletes": cache_stats["deletes"],
        "errors": cache_stats["errors"],
        "hit_rate_percent": round(hit_rate, 2),
        "total_requests": total_requests
    }


def reset_cache_statistics():
    """Reset cache statistics."""
    global cache_stats
    cache_stats = {
        "hits": 0,
        "misses": 0,
        "sets": 0,
        "deletes": 0,
        "errors": 0
    }

