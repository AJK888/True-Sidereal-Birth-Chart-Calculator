"""
Clean Famous People JSON Files

This script removes entries from JSON files that contain famous people data
if those people are no longer in the database.
"""

import json
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path to import database
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import SessionLocal, FamousPerson

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_database_names():
    """Get all famous person names from the database."""
    db = SessionLocal()
    try:
        names = {fp.name for fp in db.query(FamousPerson.name).all()}
        logger.info(f"Found {len(names)} names in database")
        return names
    finally:
        db.close()


def clean_json_file(file_path, db_names):
    """Remove entries from JSON file that don't exist in database."""
    if not os.path.exists(file_path):
        logger.warning(f"File not found: {file_path}")
        return 0, 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            logger.warning(f"File {file_path} does not contain a list, skipping")
            return 0, 0
        
        original_count = len(data)
        
        # Filter to keep only entries that exist in database
        # Handle different JSON structures
        cleaned_data = []
        removed_count = 0
        
        for entry in data:
            # Try to extract name from different possible structures
            name = None
            if isinstance(entry, dict):
                name = entry.get('name')
            elif isinstance(entry, str):
                name = entry
            
            if name and name in db_names:
                cleaned_data.append(entry)
            else:
                removed_count += 1
                if name:
                    logger.info(f"Removing {name} from {file_path}")
        
        # Write cleaned data back to file
        if removed_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Cleaned {file_path}: Removed {removed_count} entries, kept {len(cleaned_data)}")
        else:
            logger.info(f"No changes needed for {file_path}")
        
        return removed_count, len(cleaned_data)
    
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return 0, 0
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return 0, 0


def find_json_files():
    """Find all JSON files that might contain famous people data."""
    project_root = Path(__file__).parent.parent.parent
    json_files = []
    
    # Common locations for famous people JSON files
    search_paths = [
        project_root,
        project_root / "scripts",
        project_root.parent,  # Check parent directory (Github folder)
    ]
    
    # Common filenames
    common_names = [
        "famous_people_data.json",
        "scraped_data_backup.json",
        "*famous*.json",
        "*people*.json",
    ]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        # Check for specific filenames
        for name in common_names:
            if "*" in name:
                # Use glob pattern
                for file_path in search_path.rglob(name):
                    if file_path.is_file():
                        json_files.append(file_path)
            else:
                # Check exact filename
                file_path = search_path / name
                if file_path.exists() and file_path.is_file():
                    json_files.append(file_path)
    
    # Remove duplicates
    json_files = list(set(json_files))
    
    return json_files


def main():
    """Main function to clean JSON files."""
    logger.info("=" * 60)
    logger.info("CLEANING FAMOUS PEOPLE JSON FILES")
    logger.info("=" * 60)
    
    # Get names from database
    logger.info("Fetching names from database...")
    db_names = get_database_names()
    
    if not db_names:
        logger.warning("No names found in database. All entries in JSON files will be removed.")
        # Continue anyway - this means we'll remove all entries from JSON files
    
    # Find JSON files
    logger.info("Searching for JSON files...")
    json_files = find_json_files()
    
    if not json_files:
        logger.warning("No JSON files found to clean.")
        return
    
    logger.info(f"Found {len(json_files)} JSON file(s) to check:")
    for f in json_files:
        logger.info(f"  - {f}")
    
    # Clean each file
    total_removed = 0
    total_kept = 0
    
    for json_file in json_files:
        logger.info(f"\nProcessing {json_file}...")
        removed, kept = clean_json_file(json_file, db_names)
        total_removed += removed
        total_kept += kept
    
    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP COMPLETE")
    logger.info(f"Total entries removed: {total_removed}")
    logger.info(f"Total entries kept: {total_kept}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

