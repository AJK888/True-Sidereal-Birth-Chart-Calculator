"""
Alerting Service

Service for managing alerts and notifications based on metrics and thresholds.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from app.core.logging_config import setup_logger
from app.core.advanced_metrics import metrics_collector

logger = setup_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    title: str
    message: str
    severity: AlertSeverity
    source: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertingService:
    """Service for managing alerts."""
    
    def __init__(self):
        self._alerts: List[Alert] = []
        self._thresholds = {
            "error_rate": 0.05,  # 5% error rate threshold
            "response_time_p95": 2.0,  # 2 seconds p95 threshold
            "response_time_p99": 5.0,  # 5 seconds p99 threshold
            "slow_requests": 10,  # 10 slow requests threshold
            "timeout_requests": 5,  # 5 timeout requests threshold
        }
    
    def check_thresholds(self) -> List[Alert]:
        """Check metrics against thresholds and generate alerts."""
        alerts = []
        metrics = metrics_collector.get_summary()
        
        # Check endpoint error rates
        for endpoint, endpoint_metrics in metrics.get("endpoints", {}).items():
            error_rate = endpoint_metrics.get("error_rate", 0)
            if error_rate > self._thresholds["error_rate"]:
                alerts.append(Alert(
                    id=f"error_rate_{endpoint}_{datetime.utcnow().timestamp()}",
                    title=f"High Error Rate: {endpoint}",
                    message=f"Error rate {error_rate:.2%} exceeds threshold {self._thresholds['error_rate']:.2%}",
                    severity=AlertSeverity.WARNING,
                    source=endpoint,
                    metadata={"error_rate": error_rate, "threshold": self._thresholds["error_rate"]}
                ))
            
            # Check response times
            p95 = endpoint_metrics.get("p95_duration", 0)
            p99 = endpoint_metrics.get("p99_duration", 0)
            
            if p95 > self._thresholds["response_time_p95"]:
                alerts.append(Alert(
                    id=f"slow_p95_{endpoint}_{datetime.utcnow().timestamp()}",
                    title=f"Slow P95 Response Time: {endpoint}",
                    message=f"P95 response time {p95:.2f}s exceeds threshold {self._thresholds['response_time_p95']}s",
                    severity=AlertSeverity.WARNING,
                    source=endpoint,
                    metadata={"p95": p95, "threshold": self._thresholds["response_time_p95"]}
                ))
            
            if p99 > self._thresholds["response_time_p99"]:
                alerts.append(Alert(
                    id=f"slow_p99_{endpoint}_{datetime.utcnow().timestamp()}",
                    title=f"Slow P99 Response Time: {endpoint}",
                    message=f"P99 response time {p99:.2f}s exceeds threshold {self._thresholds['response_time_p99']}s",
                    severity=AlertSeverity.ERROR,
                    source=endpoint,
                    metadata={"p99": p99, "threshold": self._thresholds["response_time_p99"]}
                ))
        
        # Check slow requests
        slow_requests = metrics.get("errors", {}).get("slow_requests", [])
        if len(slow_requests) > self._thresholds["slow_requests"]:
            alerts.append(Alert(
                id=f"slow_requests_{datetime.utcnow().timestamp()}",
                title="High Number of Slow Requests",
                message=f"{len(slow_requests)} slow requests detected (threshold: {self._thresholds['slow_requests']})",
                severity=AlertSeverity.WARNING,
                source="system",
                metadata={"count": len(slow_requests), "threshold": self._thresholds["slow_requests"]}
            ))
        
        # Check timeout requests
        timeout_requests = metrics.get("errors", {}).get("timeout_requests", [])
        if len(timeout_requests) > self._thresholds["timeout_requests"]:
            alerts.append(Alert(
                id=f"timeout_requests_{datetime.utcnow().timestamp()}",
                title="High Number of Timeout Requests",
                message=f"{len(timeout_requests)} timeout requests detected (threshold: {self._thresholds['timeout_requests']})",
                severity=AlertSeverity.ERROR,
                source="system",
                metadata={"count": len(timeout_requests), "threshold": self._thresholds["timeout_requests"]}
            ))
        
        # Add new alerts
        for alert in alerts:
            self._alerts.append(alert)
            logger.warning(f"Alert generated: {alert.title} - {alert.message}")
        
        # Keep only last 1000 alerts
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]
        
        return alerts
    
    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[Alert]:
        """Get alerts with optional filtering."""
        alerts = self._alerts
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return alerts[:limit]
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                logger.info(f"Alert {alert_id} resolved")
                return True
        return False
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary statistics."""
        total = len(self._alerts)
        resolved = len([a for a in self._alerts if a.resolved])
        unresolved = total - resolved
        
        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity.value] = len([a for a in self._alerts if a.severity == severity and not a.resolved])
        
        return {
            "total": total,
            "resolved": resolved,
            "unresolved": unresolved,
            "by_severity": by_severity
        }


# Global alerting service instance
alerting_service = AlertingService()

