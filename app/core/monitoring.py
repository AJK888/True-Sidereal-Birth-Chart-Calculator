"""
Monitoring and observability for the application.

Provides metrics collection, performance monitoring, and error tracking.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)

# In-memory metrics storage (can be replaced with external service)
_metrics: Dict[str, Any] = {
    "request_counts": defaultdict(int),
    "request_durations": [],
    "error_counts": defaultdict(int),
    "endpoint_stats": defaultdict(lambda: {"count": 0, "total_duration": 0.0, "errors": 0}),
    "last_reset": datetime.now()
}

# Performance thresholds (in seconds)
SLOW_REQUEST_THRESHOLD = 2.0  # Log requests slower than 2 seconds
VERY_SLOW_REQUEST_THRESHOLD = 5.0  # Log requests slower than 5 seconds


def track_request_metrics(endpoint: str, duration: float, status_code: int, error: Optional[Exception] = None):
    """
    Track request metrics for monitoring.
    
    Args:
        endpoint: The endpoint path
        duration: Request duration in seconds
        status_code: HTTP status code
        error: Exception if request failed
    """
    # Update endpoint statistics
    stats = _metrics["endpoint_stats"][endpoint]
    stats["count"] += 1
    stats["total_duration"] += duration
    stats["errors"] += 1 if error or status_code >= 400 else 0
    
    # Track request duration
    _metrics["request_durations"].append({
        "endpoint": endpoint,
        "duration": duration,
        "status_code": status_code,
        "timestamp": datetime.now().isoformat()
    })
    
    # Keep only last 1000 requests in memory
    if len(_metrics["request_durations"]) > 1000:
        _metrics["request_durations"] = _metrics["request_durations"][-1000:]
    
    # Track slow requests
    if duration > VERY_SLOW_REQUEST_THRESHOLD:
        logger.warning(
            f"VERY SLOW REQUEST: {endpoint} took {duration:.2f}s (status: {status_code})"
        )
    elif duration > SLOW_REQUEST_THRESHOLD:
        logger.info(
            f"Slow request: {endpoint} took {duration:.2f}s (status: {status_code})"
        )
    
    # Track errors
    if error:
        error_type = type(error).__name__
        _metrics["error_counts"][f"{endpoint}:{error_type}"] += 1
        logger.error(f"Request error: {endpoint} - {error_type}: {str(error)}")


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of current metrics.
    
    Returns:
        Dictionary with metrics summary
    """
    now = datetime.now()
    time_since_reset = (now - _metrics["last_reset"]).total_seconds()
    
    # Calculate average durations per endpoint
    endpoint_averages = {}
    for endpoint, stats in _metrics["endpoint_stats"].items():
        if stats["count"] > 0:
            endpoint_averages[endpoint] = {
                "total_requests": stats["count"],
                "average_duration": stats["total_duration"] / stats["count"],
                "error_count": stats["errors"],
                "error_rate": stats["errors"] / stats["count"] if stats["count"] > 0 else 0
            }
    
    # Calculate overall statistics
    total_requests = sum(stats["count"] for stats in _metrics["endpoint_stats"].values())
    total_errors = sum(stats["errors"] for stats in _metrics["endpoint_stats"].values())
    
    recent_durations = [r["duration"] for r in _metrics["request_durations"][-100:]]
    avg_duration = sum(recent_durations) / len(recent_durations) if recent_durations else 0
    
    return {
        "timestamp": now.isoformat(),
        "time_since_reset_seconds": time_since_reset,
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate": total_errors / total_requests if total_requests > 0 else 0,
        "average_request_duration_seconds": avg_duration,
        "endpoint_statistics": endpoint_averages,
        "recent_errors": dict(list(_metrics["error_counts"].items())[-10:])
    }


def reset_metrics():
    """Reset all metrics (useful for testing or periodic resets)."""
    global _metrics
    _metrics = {
        "request_counts": defaultdict(int),
        "request_durations": [],
        "error_counts": defaultdict(int),
        "endpoint_stats": defaultdict(lambda: {"count": 0, "total_duration": 0.0, "errors": 0}),
        "last_reset": datetime.now()
    }
    logger.info("Metrics reset")


def track_performance(func):
    """
    Decorator to track function performance.
    
    Usage:
        @track_performance
        async def my_endpoint(...):
            ...
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        error = None
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            error = e
            raise
        finally:
            duration = time.time() - start_time
            # Try to extract endpoint name from function or args
            endpoint = getattr(func, "__name__", "unknown")
            if args and hasattr(args[0], "url"):
                endpoint = args[0].url.path
            track_request_metrics(endpoint, duration, 200 if not error else 500, error)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        error = None
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = e
            raise
        finally:
            duration = time.time() - start_time
            endpoint = getattr(func, "__name__", "unknown")
            if args and hasattr(args[0], "url"):
                endpoint = args[0].url.path
            track_request_metrics(endpoint, duration, 200 if not error else 500, error)
    
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

