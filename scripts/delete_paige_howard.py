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
        # Find Paige Howard
        paige = db.query(FamousPerson).filter(
            FamousPerson.name == "Paige Howard"
        ).first()
        
        if paige:
            logger.info(f"Found Paige Howard (ID: {paige.id})")
            logger.info(f"  Wikipedia URL: {paige.wikipedia_url}")
            logger.info(f"  Birth: {paige.birth_year}-{paige.birth_month}-{paige.birth_day}")
            logger.info(f"  Location: {paige.birth_location}")
            
            # Delete the record
            db.delete(paige)
            db.commit()
            logger.info("✓ Successfully deleted Paige Howard from database")
        else:
            logger.warning("Paige Howard not found in database")
        
    except Exception as e:
        logger.error(f"Error deleting Paige Howard: {e}")
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

