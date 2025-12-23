"""
Integration Service

Service for managing third-party integrations and external services.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum

from app.core.logging_config import setup_logger
from app.core.circuit_breaker_enhanced import get_circuit_breaker
from app.core.fallback import fallback_manager, FallbackStrategy

logger = setup_logger(__name__)


class IntegrationStatus(str, Enum):
    """Integration status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    FAILED = "failed"


class Integration:
    """Represents an external integration."""
    
    def __init__(
        self,
        name: str,
        service_type: str,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        status: IntegrationStatus = IntegrationStatus.ACTIVE
    ):
        self.name = name
        self.service_type = service_type
        self.endpoint = endpoint
        self.api_key = api_key
        self.status = status
        self.created_at = datetime.utcnow()
        self.last_check = None
        self.error_count = 0
        self.success_count = 0
    
    def record_success(self):
        """Record a successful call."""
        self.success_count += 1
        self.last_check = datetime.utcnow()
        if self.status == IntegrationStatus.DEGRADED:
            # Check if we should restore to active
            if self.error_count < 3:
                self.status = IntegrationStatus.ACTIVE
                self.error_count = 0
    
    def record_error(self):
        """Record an error."""
        self.error_count += 1
        self.last_check = datetime.utcnow()
        
        if self.error_count >= 5:
            self.status = IntegrationStatus.FAILED
        elif self.error_count >= 3:
            self.status = IntegrationStatus.DEGRADED
    
    def get_health(self) -> Dict[str, Any]:
        """Get integration health status."""
        total_calls = self.success_count + self.error_count
        success_rate = (
            self.success_count / total_calls * 100
            if total_calls > 0 else 0
        )
        
        return {
            "name": self.name,
            "service_type": self.service_type,
            "status": self.status.value,
            "success_rate": success_rate,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "last_check": self.last_check.isoformat() if self.last_check else None
        }


class IntegrationService:
    """Service for managing integrations."""
    
    def __init__(self):
        self._integrations: Dict[str, Integration] = {}
        self._circuit_breakers: Dict[str, Any] = {}
    
    def register_integration(
        self,
        name: str,
        service_type: str,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        circuit_breaker_config: Optional[Dict[str, Any]] = None
    ) -> Integration:
        """Register a new integration."""
        integration = Integration(
            name=name,
            service_type=service_type,
            endpoint=endpoint,
            api_key=api_key
        )
        self._integrations[name] = integration
        
        # Create circuit breaker for integration
        if circuit_breaker_config:
            cb = get_circuit_breaker(name, **circuit_breaker_config)
            self._circuit_breakers[name] = cb
        
        logger.info(f"Registered integration: {name} ({service_type})")
        return integration
    
    def get_integration(self, name: str) -> Optional[Integration]:
        """Get an integration by name."""
        return self._integrations.get(name)
    
    def list_integrations(self) -> List[Integration]:
        """List all integrations."""
        return list(self._integrations.values())
    
    def get_integration_health(self, name: str) -> Optional[Dict[str, Any]]:
        """Get health status for an integration."""
        integration = self._integrations.get(name)
        if not integration:
            return None
        
        health = integration.get_health()
        
        # Add circuit breaker metrics if available
        if name in self._circuit_breakers:
            cb = self._circuit_breakers[name]
            health["circuit_breaker"] = cb.get_metrics()
        
        return health
    
    def get_all_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status for all integrations."""
        return {
            name: self.get_integration_health(name)
            for name in self._integrations.keys()
        }
    
    def call_integration(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Call an integration function with circuit breaker protection."""
        integration = self._integrations.get(name)
        if not integration:
            raise ValueError(f"Integration {name} not found")
        
        # Check if integration is available
        if integration.status == IntegrationStatus.FAILED:
            raise Exception(f"Integration {name} is in FAILED state")
        
        # Use circuit breaker if available
        if name in self._circuit_breakers:
            cb = self._circuit_breakers[name]
            try:
                result = cb.call(func, *args, **kwargs)
                integration.record_success()
                return result
            except Exception as e:
                integration.record_error()
                raise
        else:
            # No circuit breaker, call directly
            try:
                result = func(*args, **kwargs)
                integration.record_success()
                return result
            except Exception as e:
                integration.record_error()
                raise


# Global integration service instance
integration_service = IntegrationService()

