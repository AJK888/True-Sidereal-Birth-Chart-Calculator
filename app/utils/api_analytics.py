"""
API Usage Analytics

Tracks API usage, endpoint popularity, and usage patterns.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import time

logger = logging.getLogger(__name__)


class APIUsageTracker:
    """Tracks API usage statistics."""
    
    def __init__(self):
        self.endpoint_counts = defaultdict(int)
        self.endpoint_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.user_usage = defaultdict(int)
        self.ip_usage = defaultdict(int)
        self.start_time = datetime.utcnow()
    
    def track_request(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        response_time: Optional[float] = None,
        status_code: Optional[int] = None
    ):
        """
        Track an API request.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            user_id: Optional user ID
            ip_address: Optional IP address
            response_time: Optional response time in seconds
            status_code: Optional HTTP status code
        """
        key = f"{method} {endpoint}"
        self.endpoint_counts[key] += 1
        
        if response_time is not None:
            self.endpoint_times[key].append(response_time)
            # Keep only last 1000 response times per endpoint
            if len(self.endpoint_times[key]) > 1000:
                self.endpoint_times[key] = self.endpoint_times[key][-1000:]
        
        if status_code and status_code >= 400:
            self.error_counts[key] += 1
        
        if user_id:
            self.user_usage[user_id] += 1
        
        if ip_address:
            self.ip_usage[ip_address] += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Calculate endpoint statistics
        endpoint_stats = {}
        for endpoint, count in self.endpoint_counts.items():
            times = self.endpoint_times.get(endpoint, [])
            avg_time = sum(times) / len(times) if times else 0
            min_time = min(times) if times else 0
            max_time = max(times) if times else 0
            
            endpoint_stats[endpoint] = {
                "count": count,
                "errors": self.error_counts.get(endpoint, 0),
                "avg_response_time": round(avg_time * 1000, 2),  # Convert to ms
                "min_response_time": round(min_time * 1000, 2),
                "max_response_time": round(max_time * 1000, 2),
                "error_rate": round(self.error_counts.get(endpoint, 0) / count * 100, 2) if count > 0 else 0
            }
        
        # Get top endpoints
        top_endpoints = sorted(
            self.endpoint_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Get top users
        top_users = sorted(
            self.user_usage.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "uptime_seconds": round(uptime, 2),
            "total_requests": sum(self.endpoint_counts.values()),
            "total_errors": sum(self.error_counts.values()),
            "unique_users": len(self.user_usage),
            "unique_ips": len(self.ip_usage),
            "endpoints": endpoint_stats,
            "top_endpoints": [{"endpoint": k, "count": v} for k, v in top_endpoints],
            "top_users": [{"user_id": k, "count": v} for k, v in top_users],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_endpoint_statistics(self, endpoint: str, method: str = "GET") -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific endpoint.
        
        Args:
            endpoint: Endpoint path
            method: HTTP method
        
        Returns:
            Endpoint statistics or None
        """
        key = f"{method} {endpoint}"
        if key not in self.endpoint_counts:
            return None
        
        stats = self.get_statistics()
        return stats["endpoints"].get(key)
    
    def reset(self):
        """Reset all statistics."""
        self.endpoint_counts.clear()
        self.endpoint_times.clear()
        self.error_counts.clear()
        self.user_usage.clear()
        self.ip_usage.clear()
        self.start_time = datetime.utcnow()


# Global tracker instance
_usage_tracker = APIUsageTracker()


def track_api_request(
    endpoint: str,
    method: str,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    response_time: Optional[float] = None,
    status_code: Optional[int] = None
):
    """
    Track an API request (convenience function).
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        user_id: Optional user ID
        ip_address: Optional IP address
        response_time: Optional response time in seconds
        status_code: Optional HTTP status code
    """
    _usage_tracker.track_request(
        endpoint, method, user_id, ip_address, response_time, status_code
    )


def get_api_statistics() -> Dict[str, Any]:
    """
    Get API usage statistics (convenience function).
    
    Returns:
        Dictionary with usage statistics
    """
    return _usage_tracker.get_statistics()


def get_endpoint_statistics(endpoint: str, method: str = "GET") -> Optional[Dict[str, Any]]:
    """
    Get statistics for a specific endpoint (convenience function).
    
    Args:
        endpoint: Endpoint path
        method: HTTP method
    
    Returns:
        Endpoint statistics or None
    """
    return _usage_tracker.get_endpoint_statistics(endpoint, method)


def reset_api_statistics():
    """Reset API statistics (convenience function)."""
    _usage_tracker.reset()

