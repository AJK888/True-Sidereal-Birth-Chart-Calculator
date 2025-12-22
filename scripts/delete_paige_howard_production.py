"""
Script to delete Paige Howard from the PRODUCTION famous_people database.
This script will connect to the production database (Supabase) and remove Paige Howard.

Usage:
    # Set DATABASE_URL environment variable to production database
    $env:DATABASE_URL="postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
    python scripts/delete_paige_howard_production.py
    
    OR
    
    # The script will prompt you to enter the database URL if not set
"""
import sys
import os

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_paige_howard_production():
    """Delete Paige Howard from the production famous_people table."""
    
    # Check database URL
    db_url = os.getenv("DATABASE_URL", "")
    
    if not db_url:
        logger.error("DATABASE_URL environment variable not set!")
        logger.info("Please set it to your production database URL:")
        logger.info("  Windows PowerShell: $env:DATABASE_URL='postgresql://...'")
        logger.info("  Linux/Mac: export DATABASE_URL='postgresql://...'")
        logger.info("\nOr enter the database URL now (press Enter to use default Supabase URL):")
        user_input = input().strip()
        if user_input:
            os.environ["DATABASE_URL"] = user_input
        else:
            # Use default Supabase URL from docs
            default_url = "postgresql://postgres.nfglgzrfpmtsowwacmwz:%23SynthesisAstrology1@aws-1-us-east-1.pooler.supabase.com:6543/postgres"
            logger.info(f"Using default Supabase URL")
            os.environ["DATABASE_URL"] = default_url
            # Need to reload database module to pick up new URL
            import importlib
            import database
            importlib.reload(database)
    
    db_url = os.getenv("DATABASE_URL", "")
    logger.info(f"Database URL: {db_url[:50]}..." if len(db_url) > 50 else f"Database URL: {db_url}")
    
    if "supabase" in db_url.lower() or "postgres" in db_url.lower():
        logger.info("✓ Connected to production database (PostgreSQL/Supabase)")
    else:
        logger.warning("⚠ Warning: This doesn't look like a production database!")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response != "yes":
            logger.info("Aborted.")
            return
    
    # Import after setting DATABASE_URL
    from database import SessionLocal, FamousPerson
    
    db = SessionLocal()
    try:
        # Search for Paige Howard with various name variations (case-insensitive)
        from sqlalchemy import or_, func
        
        # Try exact match first
        paige = db.query(FamousPerson).filter(
            func.lower(FamousPerson.name) == "paige howard"
        ).first()
        
        # If not found, try partial matches
        if not paige:
            logger.info("Exact match not found, searching for variations...")
            paige = db.query(FamousPerson).filter(
                or_(
                    func.lower(FamousPerson.name).like("%paige%howard%"),
                    func.lower(FamousPerson.name).like("paige howard%"),
                    func.lower(FamousPerson.name).like("%paige howard")
                )
            ).first()
        
        if paige:
            logger.info(f"Found Paige Howard (ID: {paige.id})")
            logger.info(f"  Name: {paige.name}")
            logger.info(f"  Wikipedia URL: {paige.wikipedia_url}")
            logger.info(f"  Birth: {paige.birth_year}-{paige.birth_month}-{paige.birth_day}")
            logger.info(f"  Location: {paige.birth_location}")
            
            # Confirm deletion (skip if running non-interactively)
            logger.warning("⚠ About to DELETE this record from the database!")
            try:
                confirm = input("Type 'DELETE' to confirm (or press Enter to skip confirmation): ").strip()
                if confirm and confirm != "DELETE":
                    logger.info("Deletion cancelled.")
                    return
            except (EOFError, KeyboardInterrupt):
                # Running non-interactively, proceed with deletion
                logger.info("Running non-interactively, proceeding with deletion...")
            
            # Delete the record
            db.delete(paige)
            db.commit()
            logger.info("✓ Successfully deleted Paige Howard from database")
            
            # Verify deletion
            verify = db.query(FamousPerson).filter(
                func.lower(FamousPerson.name) == "paige howard"
            ).first()
            if verify:
                logger.warning("⚠ Warning: Paige Howard still found after deletion")
            else:
                logger.info("✓ Verified: Paige Howard successfully removed")
        else:
            logger.warning("Paige Howard not found in database")
            # List all people with "paige" or "howard" in name for debugging
            similar = db.query(FamousPerson).filter(
                or_(
                    func.lower(FamousPerson.name).like("%paige%"),
                    func.lower(FamousPerson.name).like("%howard%")
                )
            ).limit(10).all()
            if similar:
                logger.info(f"Found {len(similar)} similar names (showing first 10):")
                for person in similar:
                    logger.info(f"  - {person.name} (ID: {person.id})")
        
    except Exception as e:
        logger.error(f"Error deleting Paige Howard: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Deleting Paige Howard from PRODUCTION famous_people database")
    logger.info("=" * 60)
    delete_paige_howard_production()
    logger.info("=" * 60)
    logger.info("Done!")

