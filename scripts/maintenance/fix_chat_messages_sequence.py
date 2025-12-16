"""
Fix chat_messages sequence synchronization issue in PostgreSQL.

This script resets the PostgreSQL sequence to match the maximum ID in the table.
Run this whenever you see UniqueViolation errors for chat_messages.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import SessionLocal, engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def fix_sequence():
    """Reset the chat_messages sequence to the correct value."""
    from database import DATABASE_URL, engine
    
    # Check if we're using PostgreSQL or SQLite
    is_postgres = DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')
    
    if not is_postgres:
        logger.info("Database is SQLite - sequences are handled automatically. No fix needed.")
        return True
    
    db = SessionLocal()
    try:
        # Get current max ID
        result = db.execute(text("SELECT MAX(id) FROM chat_messages"))
        max_id = result.scalar()
        max_id = max_id if max_id is not None else 0
        
        logger.info(f"Current maximum ID in chat_messages: {max_id}")
        
        # Get current sequence value (if sequence exists)
        try:
            result = db.execute(text("SELECT currval('chat_messages_id_seq')"))
            current_seq = result.scalar()
            logger.info(f"Current sequence value: {current_seq}")
        except Exception as e:
            logger.warning(f"Could not get current sequence value (sequence may not exist yet): {e}")
            current_seq = None
        
        # Reset sequence to max_id + 1
        new_seq_value = max_id + 1
        db.execute(text(f"SELECT setval('chat_messages_id_seq', {new_seq_value}, false)"))
        db.commit()
        
        # Verify
        result = db.execute(text("SELECT currval('chat_messages_id_seq')"))
        new_seq = result.scalar()
        logger.info(f"New sequence value: {new_seq}")
        
        logger.info(f"\n✓ Sequence fixed! Next insert will use ID {new_seq}")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing sequence: {e}")
        import traceback
        logger.error(traceback.format_exc())
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("FIXING CHAT_MESSAGES SEQUENCE")
    logger.info("=" * 60)
    success = fix_sequence()
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("Sequence fix completed successfully!")
        logger.info("=" * 60)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("Sequence fix failed. Please check the error above.")
        logger.error("=" * 60)
        sys.exit(1)

