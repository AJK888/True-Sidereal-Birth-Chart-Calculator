"""
Graceful Shutdown Handler

Handles graceful shutdown of the application.
"""

import logging
import signal
import asyncio
from typing import List, Callable
from contextlib import asynccontextmanager

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)

# Shutdown handlers
_shutdown_handlers: List[Callable] = []
_shutdown_in_progress = False


def register_shutdown_handler(handler: Callable):
    """Register a function to be called during shutdown."""
    _shutdown_handlers.append(handler)
    logger.debug(f"Registered shutdown handler: {handler.__name__}")


def unregister_shutdown_handler(handler: Callable):
    """Unregister a shutdown handler."""
    if handler in _shutdown_handlers:
        _shutdown_handlers.remove(handler)
        logger.debug(f"Unregistered shutdown handler: {handler.__name__}")


async def shutdown_application():
    """Execute all registered shutdown handlers."""
    global _shutdown_in_progress
    
    if _shutdown_in_progress:
        logger.warning("Shutdown already in progress")
        return
    
    _shutdown_in_progress = True
    logger.info("Starting graceful shutdown...")
    
    # Execute all shutdown handlers
    for handler in _shutdown_handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()
            logger.debug(f"Executed shutdown handler: {handler.__name__}")
        except Exception as e:
            logger.error(f"Error in shutdown handler {handler.__name__}: {str(e)}")
    
    logger.info("Graceful shutdown complete")


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Schedule shutdown
                asyncio.create_task(shutdown_application())
            else:
                loop.run_until_complete(shutdown_application())
        except Exception as e:
            logger.error(f"Error during signal-based shutdown: {str(e)}")
            # Force exit if graceful shutdown fails
            import sys
            sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("Signal handlers registered for graceful shutdown")


@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for FastAPI startup/shutdown."""
    # Startup
    logger.info("Application starting up...")
    setup_signal_handlers()
    
    # Register cleanup handlers
    from database import engine
    register_shutdown_handler(lambda: engine.dispose())
    
    yield
    
    # Shutdown
    await shutdown_application()
    logger.info("Application shut down")

