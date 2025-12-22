"""
Script to run database migrations on startup.

This script can be called during deployment to ensure the database
schema is up to date before the application starts.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command
from app.config import DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run Alembic migrations to upgrade database to latest version."""
    try:
        # Create Alembic config
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        
        # Override sqlalchemy.url with our DATABASE_URL
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        
        logger.info("Running database migrations...")
        logger.info(f"Database URL: {DATABASE_URL[:20]}...")  # Log partial URL for security
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Database migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)

