"""
Advanced Metrics Collection

Advanced metrics collection for monitoring and observability.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class MetricsCollector:
    """Advanced metrics collector."""
    
    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._lock = Lock()
        
        # Request metrics
        self.request_counts = defaultdict(int)
        self.request_durations = defaultdict(deque)
        self.request_errors = defaultdict(int)
        
        # Endpoint metrics
        self.endpoint_counts = defaultdict(int)
        self.endpoint_durations = defaultdict(deque)
        self.endpoint_errors = defaultdict(int)
        
        # Error metrics
        self.error_counts = defaultdict(int)
        self.error_types = defaultdict(int)
        
        # Performance metrics
        self.slow_requests = deque(maxlen=100)
        self.timeout_requests = deque(maxlen=100)
        
        # Custom metrics
        self.custom_metrics = defaultdict(lambda: {"value": 0, "count": 0, "min": float('inf'), "max": float('-inf')})
    
    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float
    ):
        """Record a request metric."""
        with self._lock:
            key = f"{method} {path}"
            
            # Request counts
            self.request_counts[key] += 1
            self.endpoint_counts[path] += 1
            
            # Request durations
            if len(self.request_durations[key]) >= self.max_samples:
                self.request_durations[key].popleft()
            self.request_durations[key].append(duration)
            
            if len(self.endpoint_durations[path]) >= self.max_samples:
                self.endpoint_durations[path].popleft()
            self.endpoint_durations[path].append(duration)
            
            # Error tracking
            if status_code >= 400:
                self.request_errors[key] += 1
                self.endpoint_errors[path] += 1
            
            # Slow requests (>2 seconds)
            if duration > 2.0:
                self.slow_requests.append({
                    "method": method,
                    "path": path,
                    "duration": duration,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Timeout requests (>5 seconds)
            if duration > 5.0:
                self.timeout_requests.append({
                    "method": method,
                    "path": path,
                    "duration": duration,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    def record_error(
        self,
        error_type: str,
        error_message: str,
        endpoint: Optional[str] = None
    ):
        """Record an error metric."""
        with self._lock:
            self.error_counts[error_type] += 1
            self.error_types[error_type] += 1
            
            if endpoint:
                self.endpoint_errors[endpoint] += 1
    
    def record_custom_metric(
        self,
        metric_name: str,
        value: float
    ):
        """Record a custom metric."""
        with self._lock:
            metric = self.custom_metrics[metric_name]
            metric["value"] += value
            metric["count"] += 1
            metric["min"] = min(metric["min"], value)
            metric["max"] = max(metric["max"], value)
    
    def get_request_metrics(self) -> Dict[str, Any]:
        """Get request metrics."""
        with self._lock:
            metrics = {}
            
            for key, durations in self.request_durations.items():
                if durations:
                    metrics[key] = {
                        "count": self.request_counts[key],
                        "errors": self.request_errors[key],
                        "avg_duration": sum(durations) / len(durations),
                        "min_duration": min(durations),
                        "max_duration": max(durations),
                        "p95_duration": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
                        "p99_duration": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
                    }
            
            return metrics
    
    def get_endpoint_metrics(self) -> Dict[str, Any]:
        """Get endpoint metrics."""
        with self._lock:
            metrics = {}
            
            for path, durations in self.endpoint_durations.items():
                if durations:
                    metrics[path] = {
                        "count": self.endpoint_counts[path],
                        "errors": self.endpoint_errors[path],
                        "error_rate": self.endpoint_errors[path] / self.endpoint_counts[path] if self.endpoint_counts[path] > 0 else 0,
                        "avg_duration": sum(durations) / len(durations),
                        "min_duration": min(durations),
                        "max_duration": max(durations),
                        "p95_duration": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
                        "p99_duration": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
                    }
            
            return metrics
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """Get error metrics."""
        with self._lock:
            return {
                "total_errors": sum(self.error_counts.values()),
                "error_types": dict(self.error_types),
                "error_counts": dict(self.error_counts),
                "slow_requests": list(self.slow_requests),
                "timeout_requests": list(self.timeout_requests)
            }
    
    def get_custom_metrics(self) -> Dict[str, Any]:
        """Get custom metrics."""
        with self._lock:
            metrics = {}
            for name, metric in self.custom_metrics.items():
                metrics[name] = {
                    "total": metric["value"],
                    "count": metric["count"],
                    "average": metric["value"] / metric["count"] if metric["count"] > 0 else 0,
                    "min": metric["min"] if metric["min"] != float('inf') else 0,
                    "max": metric["max"] if metric["max"] != float('-inf') else 0,
                }
            return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            "requests": self.get_request_metrics(),
            "endpoints": self.get_endpoint_metrics(),
            "errors": self.get_error_metrics(),
            "custom": self.get_custom_metrics(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self.request_counts.clear()
            self.request_durations.clear()
            self.request_errors.clear()
            self.endpoint_counts.clear()
            self.endpoint_durations.clear()
            self.endpoint_errors.clear()
            self.error_counts.clear()
            self.error_types.clear()
            self.slow_requests.clear()
            self.timeout_requests.clear()
            self.custom_metrics.clear()


# Global metrics collector instance
metrics_collector = MetricsCollector()

