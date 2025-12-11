#!/usr/bin/env python3
"""
Wrapper script to run migration with DATABASE_URL from environment.
This allows migrating production databases (Supabase) by setting DATABASE_URL.

Usage:
    # Migrate local SQLite (default)
    python scripts/migration/run_migration_with_env.py

    # Migrate production Supabase
    export DATABASE_URL="postgresql://user:pass@host:port/db"
    python scripts/migration/run_migration_with_env.py --update-all
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import after path is set
from scripts.migration.migrate_placements_aspects import main

if __name__ == "__main__":
    db_url = os.getenv("DATABASE_URL", "sqlite:///./synthesis_astrology.db")
    print(f"Using DATABASE_URL: {db_url[:50]}..." if len(db_url) > 50 else f"Using DATABASE_URL: {db_url}")
    print()
    
    # Run the migration
    main()
