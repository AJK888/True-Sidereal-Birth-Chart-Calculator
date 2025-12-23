"""
Enhanced Circuit Breaker

Enhanced circuit breaker with metrics, monitoring, and advanced features.
"""

import logging
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from functools import wraps
from collections import deque

from app.core.circuit_breaker import CircuitBreaker, CircuitState
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class EnhancedCircuitBreaker(CircuitBreaker):
    """Enhanced circuit breaker with metrics and monitoring."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        success_threshold: int = 2,
        max_history: int = 100
    ):
        super().__init__(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold
        )
        self.max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "circuit_opens": 0,
            "circuit_closes": 0,
            "circuit_half_opens": 0
        }
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function with circuit breaker protection."""
        self._metrics["total_calls"] += 1
        
        # Check circuit state
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time < self.recovery_timeout:
                self._metrics["rejected_calls"] += 1
                self._record_event("rejected", "Circuit is open")
                raise Exception(f"Circuit breaker {self.name} is OPEN")
            else:
                # Transition to half-open
                self.state = CircuitState.HALF_OPEN
                self._metrics["circuit_half_opens"] += 1
                self._record_event("half_open", "Testing recovery")
        
        # Attempt call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self._metrics["successful_calls"] += 1
        self._record_event("success", "Call succeeded")
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_success_count += 1
            if self.half_open_success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.half_open_success_count = 0
                self._metrics["circuit_closes"] += 1
                self._record_event("closed", "Circuit closed after recovery")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self._metrics["failed_calls"] += 1
        self._record_event("failure", "Call failed")
        
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during half-open, open circuit again
            self.state = CircuitState.OPEN
            self.half_open_success_count = 0
            self._metrics["circuit_opens"] += 1
            self._record_event("opened", "Circuit opened after half-open failure")
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            # Open circuit
            self.state = CircuitState.OPEN
            self._metrics["circuit_opens"] += 1
            self._record_event("opened", f"Circuit opened after {self.failure_count} failures")
    
    def _record_event(self, event_type: str, message: str):
        """Record an event in history."""
        self._history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "message": message,
            "state": self.state.value,
            "failure_count": self.failure_count
        })
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics."""
        total = self._metrics["total_calls"]
        success_rate = (
            self._metrics["successful_calls"] / total * 100
            if total > 0 else 0
        )
        
        return {
            **self._metrics,
            "success_rate": success_rate,
            "current_state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": (
                datetime.fromtimestamp(self.last_failure_time).isoformat()
                if self.last_failure_time else None
            ),
            "history_count": len(self._history)
        }
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent history."""
        return list(self._history)[-limit:]
    
    def reset(self):
        """Reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_success_count = 0
        self.last_failure_time = 0
        self._history.clear()
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "rejected_calls": 0,
            "circuit_opens": 0,
            "circuit_closes": 0,
            "circuit_half_opens": 0
        }
        logger.info(f"Circuit breaker {self.name} reset")


# Global circuit breakers registry
_circuit_breakers: Dict[str, EnhancedCircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    **kwargs
) -> EnhancedCircuitBreaker:
    """Get or create a circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = EnhancedCircuitBreaker(name=name, **kwargs)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> Dict[str, EnhancedCircuitBreaker]:
    """Get all circuit breakers."""
    return _circuit_breakers.copy()


def get_circuit_breaker_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all circuit breakers."""
    return {
        name: cb.get_metrics()
        for name, cb in _circuit_breakers.items()
    }

