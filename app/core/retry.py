"""
Retry Logic Implementation

Provides retry functionality with exponential backoff and jitter.
"""

import logging
import random
import time
from typing import Callable, Any, Optional, Type, Tuple, List
from functools import wraps
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[Tuple[Type[Exception], ...]] = None,
        retry_on_status: Optional[List[int]] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
            retry_on: Exception types to retry on
            retry_on_status: HTTP status codes to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or (Exception,)
        self.retry_on_status = retry_on_status or [500, 502, 503, 504]
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.
        
        Args:
            attempt: Attempt number (0-indexed)
        
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative
        
        return delay


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    retry_on_status: Optional[List[int]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_on: Exception types to retry on
        retry_on_status: HTTP status codes to retry on (for HTTP exceptions)
        on_retry: Callback function called on each retry
    
    Usage:
        @retry(max_attempts=3, initial_delay=1.0)
        def my_function():
            ...
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
        retry_on_status=retry_on_status
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retry_on as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        
                        # Check for HTTP status codes if applicable
                        should_retry = True
                        if hasattr(e, 'status_code'):
                            should_retry = e.status_code in config.retry_on_status
                        
                        if should_retry:
                            logger.warning(
                                f"Retry {attempt + 1}/{config.max_attempts} for {func.__name__} "
                                f"after {delay:.2f}s: {e}"
                            )
                            
                            # Call retry callback if provided
                            if on_retry:
                                try:
                                    on_retry(e, attempt + 1)
                                except Exception as callback_error:
                                    logger.warning(f"Retry callback failed: {callback_error}")
                            
                            time.sleep(delay)
                            continue
                    
                    # Don't retry or max attempts reached
                    raise
                except Exception as e:
                    # Not in retry_on list, raise immediately
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error: no exception to raise")
        
        return wrapper
    
    return decorator


def retry_async(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    retry_on_status: Optional[List[int]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator to retry async function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_on: Exception types to retry on
        retry_on_status: HTTP status codes to retry on
        on_retry: Callback function called on each retry
    
    Usage:
        @retry_async(max_attempts=3, initial_delay=1.0)
        async def my_async_function():
            ...
    """
    import asyncio
    
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
        retry_on_status=retry_on_status
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retry_on as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        
                        # Check for HTTP status codes if applicable
                        should_retry = True
                        if hasattr(e, 'status_code'):
                            should_retry = e.status_code in config.retry_on_status
                        
                        if should_retry:
                            logger.warning(
                                f"Retry {attempt + 1}/{config.max_attempts} for {func.__name__} "
                                f"after {delay:.2f}s: {e}"
                            )
                            
                            # Call retry callback if provided
                            if on_retry:
                                try:
                                    on_retry(e, attempt + 1)
                                except Exception as callback_error:
                                    logger.warning(f"Retry callback failed: {callback_error}")
                            
                            await asyncio.sleep(delay)
                            continue
                    
                    # Don't retry or max attempts reached
                    raise
                except Exception as e:
                    # Not in retry_on list, raise immediately
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error: no exception to raise")
        
        return wrapper
    
    return decorator


def retry_with_circuit_breaker(
    circuit_breaker_name: str,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    retry_on_status: Optional[List[int]] = None
):
    """
    Decorator combining retry logic with circuit breaker.
    
    Args:
        circuit_breaker_name: Name of circuit breaker to use
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_on: Exception types to retry on
        retry_on_status: HTTP status codes to retry on
    
    Usage:
        @retry_with_circuit_breaker("external_api", max_attempts=3)
        def call_external_api():
            ...
    """
    from app.core.circuit_breaker import get_circuit_breaker
    
    cb = get_circuit_breaker(circuit_breaker_name)
    retry_decorator = retry(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
        retry_on_status=retry_on_status
    )
    
    def decorator(func: Callable) -> Callable:
        retried_func = retry_decorator(func)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return cb.call(retried_func, *args, **kwargs)
        
        return wrapper
    
    return decorator

