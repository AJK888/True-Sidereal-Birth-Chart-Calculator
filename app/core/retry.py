"""
Retry Utilities

Utilities for implementing retry logic with exponential backoff.
"""

import logging
import time
import asyncio
from typing import Callable, TypeVar, Optional, List, Type, Union
from functools import wraps
from datetime import datetime, timedelta

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[List[Type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [Exception]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt."""
        delay = self.initial_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay


def retry(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        config: Retry configuration
        on_retry: Callback function called on each retry attempt
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        raise
                    
                    # Don't retry on last attempt
                    if attempt >= config.max_attempts:
                        break
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    # Call retry callback
                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception:
                            pass
                    
                    logger.warning(
                        f"Retry attempt {attempt}/{config.max_attempts} for {func.__name__}: {str(e)}"
                    )
                    
                    # Wait before retrying
                    await asyncio.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All retry attempts exhausted for {func.__name__}: {str(last_exception)}"
            )
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions):
                        raise
                    
                    # Don't retry on last attempt
                    if attempt >= config.max_attempts:
                        break
                    
                    # Calculate delay
                    delay = config.calculate_delay(attempt)
                    
                    # Call retry callback
                    if on_retry:
                        try:
                            on_retry(e, attempt)
                        except Exception:
                            pass
                    
                    logger.warning(
                        f"Retry attempt {attempt}/{config.max_attempts} for {func.__name__}: {str(e)}"
                    )
                    
                    # Wait before retrying
                    time.sleep(delay)
            
            # All retries exhausted
            logger.error(
                f"All retry attempts exhausted for {func.__name__}: {str(last_exception)}"
            )
            raise last_exception
        
        # Determine if function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def retry_with_fallback(
    fallback_func: Callable[..., T],
    config: Optional[RetryConfig] = None
):
    """
    Decorator for retrying with a fallback function.
    
    Args:
        fallback_func: Function to call if all retries fail
        config: Retry configuration
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        retry_decorator = retry(config=config)
        retried_func = retry_decorator(func)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                if asyncio.iscoroutinefunction(func):
                    return await retried_func(*args, **kwargs)
                else:
                    return retried_func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Retries exhausted for {func.__name__}, using fallback: {str(e)}"
                )
                if asyncio.iscoroutinefunction(fallback_func):
                    return await fallback_func(*args, **kwargs)
                else:
                    return fallback_func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return retried_func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Retries exhausted for {func.__name__}, using fallback: {str(e)}"
                )
                return fallback_func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
