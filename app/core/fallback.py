"""
Fallback Strategies

Utilities for implementing fallback mechanisms when primary services fail.
"""

import logging
from typing import Callable, TypeVar, Optional, Dict, Any, List
from functools import wraps
from enum import Enum

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)

T = TypeVar('T')


class FallbackStrategy(str, Enum):
    """Fallback strategy types."""
    NONE = "none"
    CACHE = "cache"
    DEFAULT = "default"
    ALTERNATIVE = "alternative"
    DEGRADE = "degrade"


class FallbackManager:
    """Manages fallback strategies for service calls."""
    
    def __init__(self):
        self._fallbacks: Dict[str, Callable] = {}
        self._strategies: Dict[str, FallbackStrategy] = {}
    
    def register_fallback(
        self,
        service_name: str,
        fallback_func: Callable,
        strategy: FallbackStrategy = FallbackStrategy.DEFAULT
    ):
        """Register a fallback function for a service."""
        self._fallbacks[service_name] = fallback_func
        self._strategies[service_name] = strategy
        logger.info(f"Registered fallback for {service_name} with strategy {strategy.value}")
    
    def get_fallback(self, service_name: str) -> Optional[Callable]:
        """Get fallback function for a service."""
        return self._fallbacks.get(service_name)
    
    def get_strategy(self, service_name: str) -> FallbackStrategy:
        """Get fallback strategy for a service."""
        return self._strategies.get(service_name, FallbackStrategy.NONE)


# Global fallback manager
fallback_manager = FallbackManager()


def with_fallback(
    service_name: str,
    fallback_func: Optional[Callable] = None,
    strategy: FallbackStrategy = FallbackStrategy.DEFAULT
):
    """
    Decorator for adding fallback behavior to a function.
    
    Args:
        service_name: Name of the service
        fallback_func: Fallback function to call
        strategy: Fallback strategy to use
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Register fallback if provided
        if fallback_func:
            fallback_manager.register_fallback(service_name, fallback_func, strategy)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Service {service_name} failed: {str(e)}")
                
                # Get fallback function
                fallback = fallback_manager.get_fallback(service_name)
                if fallback:
                    logger.info(f"Using fallback for {service_name}")
                    try:
                        if callable(fallback):
                            return await fallback(*args, **kwargs)
                        else:
                            return fallback
                    except Exception as fallback_error:
                        logger.error(f"Fallback for {service_name} also failed: {str(fallback_error)}")
                        raise fallback_error
                else:
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Service {service_name} failed: {str(e)}")
                
                # Get fallback function
                fallback = fallback_manager.get_fallback(service_name)
                if fallback:
                    logger.info(f"Using fallback for {service_name}")
                    try:
                        if callable(fallback):
                            return fallback(*args, **kwargs)
                        else:
                            return fallback
                    except Exception as fallback_error:
                        logger.error(f"Fallback for {service_name} also failed: {str(fallback_error)}")
                        raise fallback_error
                else:
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def graceful_degradation(
    min_features: List[str],
    degraded_features: Optional[Dict[str, Callable]] = None
):
    """
    Decorator for implementing graceful degradation.
    
    Args:
        min_features: List of minimum required features
        degraded_features: Dictionary of degraded feature implementations
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Feature degradation: {str(e)}")
                
                # Try degraded features
                if degraded_features:
                    for feature_name, degraded_func in degraded_features.items():
                        if feature_name in min_features:
                            continue  # Skip minimum features
                        
                        try:
                            logger.info(f"Trying degraded feature: {feature_name}")
                            return await degraded_func(*args, **kwargs)
                        except Exception:
                            continue
                
                # If minimum features are required, raise error
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Feature degradation: {str(e)}")
                
                # Try degraded features
                if degraded_features:
                    for feature_name, degraded_func in degraded_features.items():
                        if feature_name in min_features:
                            continue  # Skip minimum features
                        
                        try:
                            logger.info(f"Trying degraded feature: {feature_name}")
                            return degraded_func(*args, **kwargs)
                        except Exception:
                            continue
                
                # If minimum features are required, raise error
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

