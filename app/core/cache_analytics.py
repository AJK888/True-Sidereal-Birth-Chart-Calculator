"""
Cache Analytics

Track and analyze cache performance metrics.
"""

import logging
import time
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache statistics
_cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "deletes": 0,
    "errors": 0,
    "by_key_pattern": defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0}),
    "by_hour": defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0}),
    "start_time": time.time()
}


def track_cache_hit(key: str, source: str = "unknown"):
    """
    Track a cache hit.
    
    Args:
        key: Cache key
        source: Cache source (e.g., "l1", "l2", "redis")
    """
    _cache_stats["hits"] += 1
    
    # Track by key pattern
    key_pattern = _get_key_pattern(key)
    _cache_stats["by_key_pattern"][key_pattern]["hits"] += 1
    
    # Track by hour
    hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
    _cache_stats["by_hour"][hour]["hits"] += 1


def track_cache_miss(key: str):
    """
    Track a cache miss.
    
    Args:
        key: Cache key
    """
    _cache_stats["misses"] += 1
    
    # Track by key pattern
    key_pattern = _get_key_pattern(key)
    _cache_stats["by_key_pattern"][key_pattern]["misses"] += 1
    
    # Track by hour
    hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
    _cache_stats["by_hour"][hour]["misses"] += 1


def track_cache_set(key: str):
    """
    Track a cache set operation.
    
    Args:
        key: Cache key
    """
    _cache_stats["sets"] += 1
    
    # Track by key pattern
    key_pattern = _get_key_pattern(key)
    _cache_stats["by_key_pattern"][key_pattern]["sets"] += 1
    
    # Track by hour
    hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
    _cache_stats["by_hour"][hour]["sets"] += 1


def track_cache_delete(key: str):
    """
    Track a cache delete operation.
    
    Args:
        key: Cache key
    """
    _cache_stats["deletes"] += 1


def track_cache_error(key: str, error: str):
    """
    Track a cache error.
    
    Args:
        key: Cache key
        error: Error message
    """
    _cache_stats["errors"] += 1
    logger.warning(f"Cache error for key {key}: {error}")


def _get_key_pattern(key: str) -> str:
    """
    Extract key pattern from cache key.
    
    Args:
        key: Cache key
    
    Returns:
        Key pattern (e.g., "chart:", "reading:", "famous_people:")
    """
    if ":" in key:
        return key.split(":")[0] + ":"
    return "unknown:"


def get_cache_statistics() -> Dict[str, Any]:
    """
    Get cache performance statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    total_requests = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = (_cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
    
    uptime_seconds = time.time() - _cache_stats["start_time"]
    uptime_hours = uptime_seconds / 3600
    
    return {
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "sets": _cache_stats["sets"],
        "deletes": _cache_stats["deletes"],
        "errors": _cache_stats["errors"],
        "total_requests": total_requests,
        "hit_rate_percent": round(hit_rate, 2),
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_hours": round(uptime_hours, 2),
        "requests_per_hour": round(total_requests / uptime_hours, 2) if uptime_hours > 0 else 0,
        "by_key_pattern": {
            pattern: {
                "hits": stats["hits"],
                "misses": stats["misses"],
                "sets": stats["sets"],
                "total": stats["hits"] + stats["misses"],
                "hit_rate": round(
                    (stats["hits"] / (stats["hits"] + stats["misses"]) * 100)
                    if (stats["hits"] + stats["misses"]) > 0 else 0,
                    2
                )
            }
            for pattern, stats in _cache_stats["by_key_pattern"].items()
        },
        "by_hour": dict(_cache_stats["by_hour"])
    }


def get_cache_hit_rate(key_pattern: Optional[str] = None) -> float:
    """
    Get cache hit rate.
    
    Args:
        key_pattern: Optional key pattern to filter by
    
    Returns:
        Hit rate as percentage (0-100)
    """
    if key_pattern:
        pattern_stats = _cache_stats["by_key_pattern"].get(key_pattern, {})
        total = pattern_stats.get("hits", 0) + pattern_stats.get("misses", 0)
        if total == 0:
            return 0.0
        return round((pattern_stats.get("hits", 0) / total) * 100, 2)
    
    total_requests = _cache_stats["hits"] + _cache_stats["misses"]
    if total_requests == 0:
        return 0.0
    return round((_cache_stats["hits"] / total_requests) * 100, 2)


def reset_cache_statistics():
    """Reset cache statistics."""
    global _cache_stats
    _cache_stats = {
        "hits": 0,
        "misses": 0,
        "sets": 0,
        "deletes": 0,
        "errors": 0,
        "by_key_pattern": defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0}),
        "by_hour": defaultdict(lambda: {"hits": 0, "misses": 0, "sets": 0}),
        "start_time": time.time()
    }
    logger.info("Cache statistics reset")


def get_cache_recommendations() -> List[str]:
    """
    Get cache optimization recommendations.
    
    Returns:
        List of recommendation strings
    """
    recommendations = []
    stats = get_cache_statistics()
    
    # Check overall hit rate
    hit_rate = stats["hit_rate_percent"]
    if hit_rate < 50:
        recommendations.append(
            f"Cache hit rate is low ({hit_rate}%). Consider increasing cache size or TTL."
        )
    elif hit_rate < 70:
        recommendations.append(
            f"Cache hit rate could be improved ({hit_rate}%). Consider cache warming."
        )
    
    # Check key patterns
    for pattern, pattern_stats in stats["by_key_pattern"].items():
        pattern_hit_rate = pattern_stats["hit_rate"]
        if pattern_hit_rate < 50 and pattern_stats["total"] > 100:
            recommendations.append(
                f"Key pattern '{pattern}' has low hit rate ({pattern_hit_rate}%). "
                f"Consider adjusting cache strategy for this pattern."
            )
    
    # Check for errors
    if stats["errors"] > 0:
        error_rate = (stats["errors"] / stats["total_requests"]) * 100 if stats["total_requests"] > 0 else 0
        if error_rate > 1:
            recommendations.append(
                f"Cache error rate is high ({error_rate:.2f}%). Check cache configuration."
            )
    
    return recommendations

