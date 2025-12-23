"""
Error Aggregator

Aggregates and analyzes errors for monitoring and debugging.
"""

import logging
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from threading import Lock

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class ErrorAggregator:
    """Aggregates errors for analysis."""
    
    def __init__(self, max_errors: int = 1000):
        self.max_errors = max_errors
        self._lock = Lock()
        
        # Error storage
        self._errors: deque = deque(maxlen=max_errors)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._error_by_endpoint: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._error_by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    def record_error(
        self,
        error: Exception,
        endpoint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Record an error."""
        error_type = type(error).__name__
        error_message = str(error)
        error_traceback = traceback.format_exc()
        
        error_data = {
            "type": error_type,
            "message": error_message,
            "traceback": error_traceback,
            "endpoint": endpoint,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        with self._lock:
            self._errors.append(error_data)
            self._error_counts[error_type] += 1
            
            if endpoint:
                if len(self._error_by_endpoint[endpoint]) >= 100:
                    self._error_by_endpoint[endpoint].pop(0)
                self._error_by_endpoint[endpoint].append(error_data)
            
            if len(self._error_by_type[error_type]) >= 100:
                self._error_by_type[error_type].pop(0)
            self._error_by_type[error_type].append(error_data)
    
    def get_error_summary(
        self,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get error summary for the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with self._lock:
            recent_errors = [
                e for e in self._errors
                if datetime.fromisoformat(e["timestamp"]) >= cutoff
            ]
            
            return {
                "total_errors": len(recent_errors),
                "error_types": dict(self._error_counts),
                "errors_by_endpoint": {
                    endpoint: len(errors)
                    for endpoint, errors in self._error_by_endpoint.items()
                },
                "recent_errors": recent_errors[-50:],  # Last 50 errors
                "period_hours": hours
            }
    
    def get_errors_by_type(
        self,
        error_type: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get errors of a specific type."""
        with self._lock:
            return self._error_by_type.get(error_type, [])[-limit:]
    
    def get_errors_by_endpoint(
        self,
        endpoint: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get errors for a specific endpoint."""
        with self._lock:
            return self._error_by_endpoint.get(endpoint, [])[-limit:]
    
    def get_top_errors(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top errors by frequency."""
        with self._lock:
            sorted_errors = sorted(
                self._error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            return [
                {
                    "type": error_type,
                    "count": count,
                    "recent": self._error_by_type[error_type][-5:]  # Last 5 of this type
                }
                for error_type, count in sorted_errors
            ]


# Global error aggregator instance
error_aggregator = ErrorAggregator()

