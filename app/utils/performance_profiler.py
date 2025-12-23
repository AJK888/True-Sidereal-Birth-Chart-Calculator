"""
Performance Profiling Utilities

Tools for profiling and analyzing application performance.
"""

import logging
import time
import functools
import traceback
from typing import Dict, Any, Optional, Callable, List
from collections import defaultdict
from datetime import datetime, timedelta
import sys
import cProfile
import pstats
import io

logger = logging.getLogger(__name__)

# Performance metrics storage
_performance_metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_slow_operations: List[Dict[str, Any]] = []
_profiler_enabled = False
_active_profilers: Dict[str, cProfile.Profile] = {}


def enable_profiling(enabled: bool = True):
    """
    Enable or disable performance profiling.
    
    Args:
        enabled: Whether to enable profiling
    """
    global _profiler_enabled
    _profiler_enabled = enabled
    logger.info(f"Performance profiling {'enabled' if enabled else 'disabled'}")


def profile_function(func: Optional[Callable] = None, threshold_ms: float = 100.0):
    """
    Decorator to profile function execution time.
    
    Args:
        func: Function to profile
        threshold_ms: Log warning if execution exceeds this threshold (ms)
    
    Usage:
        @profile_function(threshold_ms=50)
        def my_function():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = f"{f.__module__}.{f.__name__}"
            
            try:
                result = f(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Record metric
                _performance_metrics[function_name].append({
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                })
                
                # Track slow operations
                if duration_ms > threshold_ms:
                    _slow_operations.append({
                        "function": function_name,
                        "duration_ms": duration_ms,
                        "timestamp": datetime.utcnow().isoformat(),
                        "args": str(args)[:200],  # Limit length
                        "kwargs": str(kwargs)[:200]
                    })
                    logger.warning(
                        f"Slow operation detected: {function_name} took {duration_ms:.2f}ms"
                    )
                
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Record error metric
                _performance_metrics[function_name].append({
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False,
                    "error": str(e)
                })
                
                logger.error(
                    f"Error in {function_name} after {duration_ms:.2f}ms: {e}",
                    exc_info=True
                )
                raise
        
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)


def start_profiler(name: str) -> str:
    """
    Start a profiler for a specific operation.
    
    Args:
        name: Name identifier for the profiler
    
    Returns:
        Profiler ID
    """
    if not _profiler_enabled:
        return ""
    
    profiler_id = f"{name}_{int(time.time() * 1000)}"
    profiler = cProfile.Profile()
    profiler.enable()
    _active_profilers[profiler_id] = profiler
    
    return profiler_id


def stop_profiler(profiler_id: str) -> Optional[Dict[str, Any]]:
    """
    Stop a profiler and get results.
    
    Args:
        profiler_id: Profiler ID returned by start_profiler
    
    Returns:
        Profiling results or None if profiler not found
    """
    if not profiler_id or profiler_id not in _active_profilers:
        return None
    
    profiler = _active_profilers.pop(profiler_id)
    profiler.disable()
    
    # Get stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions
    
    return {
        "profiler_id": profiler_id,
        "stats": s.getvalue(),
        "total_calls": ps.total_calls,
        "total_time": ps.total_tt
    }


def get_performance_statistics() -> Dict[str, Any]:
    """
    Get aggregated performance statistics.
    
    Returns:
        Dictionary with performance statistics
    """
    stats = {}
    
    for function_name, metrics in _performance_metrics.items():
        if not metrics:
            continue
        
        durations = [m["duration_ms"] for m in metrics]
        successes = [m for m in metrics if m.get("success", True)]
        errors = [m for m in metrics if not m.get("success", True)]
        
        stats[function_name] = {
            "count": len(metrics),
            "success_count": len(successes),
            "error_count": len(errors),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "p50_duration_ms": sorted(durations)[len(durations) // 2] if durations else 0,
            "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
            "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
            "error_rate": len(errors) / len(metrics) if metrics else 0
        }
    
    return {
        "total_functions": len(stats),
        "total_operations": sum(len(metrics) for metrics in _performance_metrics.values()),
        "slow_operations_count": len(_slow_operations),
        "functions": stats
    }


def get_slow_operations(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Get the slowest operations.
    
    Args:
        limit: Maximum number of operations to return
    
    Returns:
        List of slow operation details
    """
    return sorted(_slow_operations, key=lambda x: x["duration_ms"], reverse=True)[:limit]


def get_function_statistics(function_name: str) -> Optional[Dict[str, Any]]:
    """
    Get statistics for a specific function.
    
    Args:
        function_name: Name of the function
    
    Returns:
        Function statistics or None if not found
    """
    if function_name not in _performance_metrics:
        return None
    
    metrics = _performance_metrics[function_name]
    if not metrics:
        return None
    
    durations = [m["duration_ms"] for m in metrics]
    successes = [m for m in metrics if m.get("success", True)]
    errors = [m for m in metrics if not m.get("success", True)]
    
    return {
        "function_name": function_name,
        "count": len(metrics),
        "success_count": len(successes),
        "error_count": len(errors),
        "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
        "min_duration_ms": min(durations) if durations else 0,
        "max_duration_ms": max(durations) if durations else 0,
        "p50_duration_ms": sorted(durations)[len(durations) // 2] if durations else 0,
        "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
        "p99_duration_ms": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
        "error_rate": len(errors) / len(metrics) if metrics else 0,
        "recent_operations": metrics[-10:]  # Last 10 operations
    }


def reset_performance_metrics():
    """Reset all performance metrics."""
    global _performance_metrics, _slow_operations
    _performance_metrics = defaultdict(list)
    _slow_operations = []
    logger.info("Performance metrics reset")


def get_resource_usage() -> Dict[str, Any]:
    """
    Get current resource usage statistics.
    
    Returns:
        Dictionary with resource usage information
    """
    try:
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Memory info
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()
        
        # CPU info
        cpu_percent = process.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # System memory
        system_memory = psutil.virtual_memory()
        
        # System CPU
        system_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        
        return {
            "process": {
                "memory_mb": round(memory_info.rss / 1024 / 1024, 2),
                "memory_percent": round(memory_percent, 2),
                "cpu_percent": round(cpu_percent, 2),
                "threads": process.num_threads(),
                "open_files": len(process.open_files())
            },
            "system": {
                "memory_total_mb": round(system_memory.total / 1024 / 1024, 2),
                "memory_available_mb": round(system_memory.available / 1024 / 1024, 2),
                "memory_percent": round(system_memory.percent, 2),
                "cpu_count": cpu_count,
                "cpu_percent": round(sum(system_cpu) / len(system_cpu), 2) if system_cpu else 0,
                "cpu_per_core": [round(cpu, 2) for cpu in system_cpu] if system_cpu else []
            }
        }
    except ImportError:
        logger.warning("psutil not available, resource usage tracking disabled")
        return {
            "error": "psutil not installed",
            "message": "Install psutil to enable resource usage tracking"
        }
    except Exception as e:
        logger.error(f"Error getting resource usage: {e}", exc_info=True)
        return {
            "error": str(e)
        }


def get_performance_recommendations() -> List[str]:
    """
    Get performance optimization recommendations.
    
    Returns:
        List of recommendation strings
    """
    recommendations = []
    stats = get_performance_statistics()
    
    # Check for slow functions
    for function_name, function_stats in stats.get("functions", {}).items():
        avg_duration = function_stats.get("avg_duration_ms", 0)
        p95_duration = function_stats.get("p95_duration_ms", 0)
        error_rate = function_stats.get("error_rate", 0)
        count = function_stats.get("count", 0)
        
        # Recommend optimization for slow functions
        if avg_duration > 1000 and count > 10:
            recommendations.append(
                f"Function '{function_name}' has high average duration ({avg_duration:.2f}ms). "
                f"Consider optimization."
            )
        
        # Recommend investigation for high p95
        if p95_duration > 2000 and count > 10:
            recommendations.append(
                f"Function '{function_name}' has high p95 duration ({p95_duration:.2f}ms). "
                f"Investigate performance spikes."
            )
        
        # Recommend error investigation
        if error_rate > 0.1 and count > 10:
            recommendations.append(
                f"Function '{function_name}' has high error rate ({error_rate*100:.1f}%). "
                f"Investigate errors."
            )
    
    # Check for many slow operations
    slow_count = stats.get("slow_operations_count", 0)
    if slow_count > 50:
        recommendations.append(
            f"Many slow operations detected ({slow_count}). Consider performance review."
        )
    
    return recommendations

