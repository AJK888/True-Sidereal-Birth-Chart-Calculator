"""
Script to create the initial Alembic migration from the current database schema.

This script helps create the first migration that captures the current state
of all database models.

Usage:
    python scripts/create_initial_migration.py
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


def create_initial_migration():
    """Create the initial Alembic migration from current models."""
    try:
        # Create Alembic config
        alembic_cfg = Config(str(project_root / "alembic.ini"))
        
        # Override sqlalchemy.url with our DATABASE_URL
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        
        logger.info("Creating initial migration from current schema...")
        logger.info(f"Database URL: {DATABASE_URL[:20]}...")  # Log partial URL for security
        
        # Create migration
        command.revision(
            alembic_cfg,
            autogenerate=True,
            message="Initial schema"
        )
        
        logger.info("Initial migration created successfully!")
        logger.info("Review the migration file in app/db/migrations/versions/")
        logger.info("Then run: alembic upgrade head")
        return True
    except Exception as e:
        logger.error(f"Failed to create migration: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = create_initial_migration()
    sys.exit(0 if success else 1)

