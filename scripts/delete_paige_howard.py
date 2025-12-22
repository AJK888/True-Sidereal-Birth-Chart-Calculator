"""
Script to delete Paige Howard from the famous_people database.
Her birth information is incorrect and she is not famous enough to keep.
"""
import sys
import os

# Add parent directory to path to import database modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_paige_howard():
    """Delete Paige Howard from the famous_people table."""
    db = SessionLocal()
    try:
        # Check which database we're connected to
        db_url = os.getenv("DATABASE_URL", "sqlite:///./synthesis_astrology.db")
        if "supabase" in db_url.lower() or "postgres" in db_url.lower():
            logger.info("Connected to production database (PostgreSQL/Supabase)")
        else:
            logger.info("Connected to local database (SQLite)")
        
        # Search for Paige Howard with various name variations (case-insensitive, with/without spaces)
        from sqlalchemy import or_, func
        
        # Try exact match first
        paige = db.query(FamousPerson).filter(
            func.lower(FamousPerson.name) == "paige howard"
        ).first()
        
        # If not found, try partial matches
        if not paige:
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
            
            # Delete the record
            db.delete(paige)
            db.commit()
            logger.info("✓ Successfully deleted Paige Howard from database")
            
            # Verify deletion
            verify = db.query(FamousPerson).filter(
                func.lower(FamousPerson.name) == "paige howard"
            ).first()
            if verify:
                logger.warning("⚠ Warning: Paige Howard still found after deletion (transaction may need commit)")
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
            ).all()
            if similar:
                logger.info(f"Found {len(similar)} similar names:")
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
    logger.info("Deleting Paige Howard from famous_people database")
    logger.info("=" * 60)
    delete_paige_howard()
    logger.info("=" * 60)
    logger.info("Done!")

