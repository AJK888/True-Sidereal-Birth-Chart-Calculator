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
            
            # Track API usage analytics
            try:
                from app.utils.api_analytics import track_api_request
                from slowapi.util import get_remote_address
                
                user_id = getattr(request.state, "user_id", None)
                ip_address = get_remote_address(request)
                
                track_api_request(
                    endpoint=endpoint,
                    method=request.method,
                    user_id=user_id,
                    ip_address=ip_address,
                    response_time=duration,
                    status_code=status_code
                )
            except Exception as e:
                # Don't fail request if analytics tracking fails
                logger.debug(f"API analytics tracking failed: {e}")
            
            # Track analytics event (if analytics service exists)
            try:
                from app.services.analytics_service import track_event
                user_id = getattr(request.state, "user_id", None)
                track_event(
                    event_type=f"api.request",
                    user_id=user_id,
                    metadata={
                        "endpoint": endpoint,
                        "method": request.method,
                        "status_code": status_code,
                        "response_time": duration
                    }
                )
            except (ImportError, Exception) as e:
                # Don't fail request if analytics tracking fails
                logger.debug(f"Analytics tracking failed: {e}")

