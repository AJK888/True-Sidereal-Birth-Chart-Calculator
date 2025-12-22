"""
Standardized logging configuration for the application.

This module provides consistent logging setup across all services.
"""

import sys
import logging
from typing import Optional

# Import centralized configuration
from app.config import LOG_LEVEL, LOGTAIL_HOST, LOGTAIL_PORT

try:
    from logtail import LogtailHandler
except ImportError:
    LogtailHandler = None

# Get LOGTAIL_API_KEY from config (if available)
try:
    from app.config import LOGTAIL_API_KEY
except ImportError:
    LOGTAIL_API_KEY = None


def setup_logger(
    name: str,
    level: Optional[int] = None,
    logtail_token: Optional[str] = None,
    logtail_host: Optional[str] = None
) -> logging.Logger:
    """
    Set up a standardized logger with console and optional Logtail handlers.
    
    Args:
        name: Logger name (typically __name__)
        level: Logging level (defaults to INFO, or LOG_LEVEL env var)
        logtail_token: Logtail source token (defaults to LOGTAIL_SOURCE_TOKEN env var)
        logtail_host: Logtail host (defaults to LOGTAIL_HOST env var or default host)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Set log level
    if level is None:
        level_str = LOG_LEVEL.upper() if LOG_LEVEL else "INFO"
        level = getattr(logging, level_str, logging.INFO)
    logger.setLevel(level)
    
    # Prevent duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Always add console handler for Render visibility
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Optionally add Logtail handler
    if logtail_token is None:
        logtail_token = LOGTAIL_API_KEY  # Use centralized config
    
    if logtail_token and LogtailHandler:
        if logtail_host is None:
            # Use centralized config with fallback
            logtail_host = LOGTAIL_HOST or "https://s1450016.eu-nbg-2.betterstackdata.com"
        
        try:
            logtail_handler = LogtailHandler(
                source_token=logtail_token,
                host=logtail_host
            )
            logtail_handler.setLevel(level)
            logger.addHandler(logtail_handler)
        except Exception as e:
            # Don't fail if Logtail setup fails
            logger.warning(f"Failed to set up Logtail handler: {e}")
    
    # Ensure logs propagate to root logger
    logger.propagate = True
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with standardized configuration.
    
    Convenience function that uses default settings.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return setup_logger(name)


# Structured logging helpers
def log_function_call(logger: logging.Logger, function_name: str, **kwargs):
    """Log a function call with structured data."""
    logger.debug(f"Calling {function_name} with args: {kwargs}")


def log_function_result(logger: logging.Logger, function_name: str, result_summary: str, **kwargs):
    """Log a function result with structured data."""
    logger.debug(f"{function_name} completed: {result_summary}", extra=kwargs)


def log_error_with_context(logger: logging.Logger, error: Exception, context: dict):
    """Log an error with additional context."""
    logger.error(
        f"{type(error).__name__}: {str(error)}",
        exc_info=True,
        extra=context
    )

