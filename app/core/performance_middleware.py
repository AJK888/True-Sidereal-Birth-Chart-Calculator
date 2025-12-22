"""
Performance monitoring middleware for FastAPI.

Tracks request durations, counts, and performance metrics.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.monitoring import track_request_metrics

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track request performance metrics.
    
    Tracks:
    - Request duration
    - Request count per endpoint
    - Error rates
    - Slow requests
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request performance."""
        start_time = time.time()
        endpoint = request.url.path
        
        # Skip metrics for health check endpoints
        if endpoint in ["/ping", "/", "/metrics"]:
            return await call_next(request)
        
        error = None
        status_code = 200
        
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            error = e
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            track_request_metrics(endpoint, duration, status_code, error)

