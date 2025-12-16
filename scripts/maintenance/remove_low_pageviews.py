"""
Remove famous people with less than 15000 pageviews from the database.

Usage:
    python scripts/maintenance/remove_low_pageviews.py [--include-null] [--dry-run]

Options:
    --include-null    Also delete records with NULL pageviews (default: False)
    --dry-run         Show what would be deleted without actually deleting
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson
from sqlalchemy import or_, and_

def remove_low_pageviews(threshold: int = 15000, include_null: bool = False, dry_run: bool = False, confirm: bool = True):
    """
    Remove famous people with pageviews less than the threshold.
    
    Args:
        threshold: Minimum pageviews to keep (default: 15000)
        include_null: If True, also delete records with NULL pageviews
        dry_run: If True, only show what would be deleted without deleting
        confirm: If False, skip confirmation prompt (use with caution)
    """
    db = SessionLocal()
    
    try:
        # Get total count before deletion
        total_before = db.query(FamousPerson).count()
        
        # Build query for records to delete
        if include_null:
            # Delete records where page_views < threshold OR page_views IS NULL
            records_to_delete = db.query(FamousPerson).filter(
                or_(
                    FamousPerson.page_views < threshold,
                    FamousPerson.page_views.is_(None)
                )
            ).all()
        else:
            # Only delete records where page_views < threshold (not NULL)
            records_to_delete = db.query(FamousPerson).filter(
                and_(
                    FamousPerson.page_views.isnot(None),
                    FamousPerson.page_views < threshold
                )
            ).all()
        
        delete_count = len(records_to_delete)
        
        # Show statistics
        print("=" * 80)
        print("REMOVE LOW PAGEVIEWS")
        print("=" * 80)
        print(f"Threshold: {threshold:,} pageviews")
        print(f"Include NULL values: {include_null}")
        print(f"Mode: {'DRY RUN' if dry_run else 'DELETE'}")
        print()
        print(f"Total records before: {total_before:,}")
        print(f"Records to delete: {delete_count:,}")
        
        if delete_count > 0:
            # Show breakdown
            null_count = sum(1 for r in records_to_delete if r.page_views is None)
            low_count = delete_count - null_count
            
            print(f"  - Records with NULL pageviews: {null_count:,}")
            print(f"  - Records with pageviews < {threshold:,}: {low_count:,}")
            print()
            
            # Show some examples
            print("Sample records to be deleted:")
            sample_count = min(10, delete_count)
            for idx, person in enumerate(records_to_delete[:sample_count], 1):
                pageviews_str = f"{person.page_views:,}" if person.page_views is not None else "NULL"
                print(f"  {idx:2d}. {person.name:40s} - {pageviews_str:>12s} views")
            
            if delete_count > sample_count:
                print(f"  ... and {delete_count - sample_count:,} more")
            
            print()
            
            if not dry_run:
                # Confirm deletion
                if confirm:
                    print("WARNING: This will permanently delete these records!")
                    response = input("Type 'DELETE' to confirm: ")
                    
                    if response != 'DELETE':
                        print("Deletion cancelled.")
                        return
                else:
                    print("WARNING: Proceeding with deletion (--yes flag used)...")
                
                # Delete records
                for person in records_to_delete:
                    db.delete(person)
                
                db.commit()
                print()
                print(f"[OK] Successfully deleted {delete_count:,} records")
            else:
                print("DRY RUN: No records were actually deleted.")
        else:
            print("[OK] No records found matching deletion criteria")
        
        # Show final statistics
        if not dry_run and delete_count > 0:
            total_after = db.query(FamousPerson).count()
            print()
            print(f"Total records after: {total_after:,}")
            print(f"Records remaining: {total_after:,}")
            
            # Show new statistics
            remaining_with_pageviews = db.query(FamousPerson).filter(
                FamousPerson.page_views.isnot(None),
                FamousPerson.page_views >= threshold
            ).count()
            
            print(f"Records with pageviews >= {threshold:,}: {remaining_with_pageviews:,}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove famous people with less than 15000 pageviews",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be deleted
  python scripts/maintenance/remove_low_pageviews.py --dry-run
  
  # Delete records with pageviews < 15000 (excluding NULL)
  python scripts/maintenance/remove_low_pageviews.py
  
  # Delete records with pageviews < 15000 AND NULL values
  python scripts/maintenance/remove_low_pageviews.py --include-null
        """
    )
    
    parser.add_argument(
        "--threshold",
        type=int,
        default=15000,
        help="Minimum pageviews threshold (default: 15000)"
    )
    
    parser.add_argument(
        "--include-null",
        action="store_true",
        help="Also delete records with NULL pageviews"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (use with caution)"
    )
    
    args = parser.parse_args()
    
    remove_low_pageviews(
        threshold=args.threshold,
        include_null=args.include_null,
        dry_run=args.dry_run,
        confirm=not args.yes
    )

