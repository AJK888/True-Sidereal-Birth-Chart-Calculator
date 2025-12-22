"""
Metrics collection utilities.

Provides functions for collecting and reporting application metrics.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.monitoring import get_metrics_summary, reset_metrics

logger = logging.getLogger(__name__)


def get_health_metrics() -> Dict[str, Any]:
    """
    Get health check metrics.
    
    Returns:
        Dictionary with health metrics
    """
    metrics = get_metrics_summary()
    
    # Determine health status
    error_rate = metrics.get("error_rate", 0)
    avg_duration = metrics.get("average_request_duration_seconds", 0)
    
    health_status = "healthy"
    if error_rate > 0.1:  # More than 10% error rate
        health_status = "degraded"
    elif error_rate > 0.05:  # More than 5% error rate
        health_status = "warning"
    
    if avg_duration > 5.0:  # Average request > 5 seconds
        health_status = "degraded"
    elif avg_duration > 2.0:  # Average request > 2 seconds
        if health_status == "healthy":
            health_status = "warning"
    
    return {
        "status": health_status,
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics
    }


def log_performance_summary():
    """Log a summary of performance metrics."""
    metrics = get_metrics_summary()
    
    logger.info("=" * 60)
    logger.info("Performance Metrics Summary")
    logger.info("=" * 60)
    logger.info(f"Total Requests: {metrics['total_requests']}")
    logger.info(f"Total Errors: {metrics['total_errors']}")
    logger.info(f"Error Rate: {metrics['error_rate']:.2%}")
    logger.info(f"Average Duration: {metrics['average_request_duration_seconds']:.3f}s")
    logger.info("=" * 60)
    
    if metrics.get("endpoint_statistics"):
        logger.info("Top Endpoints:")
        sorted_endpoints = sorted(
            metrics["endpoint_statistics"].items(),
            key=lambda x: x[1]["total_requests"],
            reverse=True
        )[:10]
        
        for endpoint, stats in sorted_endpoints:
            logger.info(
                f"  {endpoint}: "
                f"{stats['total_requests']} requests, "
                f"{stats['average_duration']:.3f}s avg, "
                f"{stats['error_count']} errors"
            )
        logger.info("=" * 60)

