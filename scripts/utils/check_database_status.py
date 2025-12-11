"""Check if database schema is up to date with current model"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db
from sqlalchemy import inspect, text

def check_database_status():
    """Check if database schema matches the current model."""
    print("=" * 60)
    print("DATABASE STATUS CHECK")
    print("=" * 60)
    
    # Initialize database (this will create missing tables/columns)
    init_db()
    
    db = SessionLocal()
    inspector = inspect(db.bind)
    
    try:
        # Check if famous_people table exists
        tables = inspector.get_table_names()
        if 'famous_people' not in tables:
            print("\n✗ Table 'famous_people' does not exist!")
            print("  Run: init_db() to create tables")
            return
        
        print("\n✓ Table 'famous_people' exists")
        
        # Get current columns
        columns = {col['name']: col for col in inspector.get_columns('famous_people')}
        print(f"\nCurrent columns in database: {len(columns)}")
        
        # Expected columns (minimal schema - only Sun, Moon, and JSON)
        expected_columns = [
            'id', 'name', 'wikipedia_url', 'occupation',
            'birth_year', 'birth_month', 'birth_day',
            'birth_hour', 'birth_minute', 'birth_location', 'unknown_time',
            'chart_data_json', 'planetary_placements_json', 'top_aspects_json',
            'sun_sign_sidereal', 'sun_sign_tropical',
            'moon_sign_sidereal', 'moon_sign_tropical',
            'life_path_number', 'day_number',
            'chinese_zodiac_animal',
            'page_views', 'created_at', 'updated_at'
        ]
        
        # Columns that should NOT exist (removed to minimize database)
        unwanted_columns = [
            'rising_sign_sidereal', 'rising_sign_tropical',
            'mercury_sign_sidereal', 'mercury_sign_tropical',
            'venus_sign_sidereal', 'venus_sign_tropical',
            'mars_sign_sidereal', 'mars_sign_tropical',
            'jupiter_sign_sidereal', 'jupiter_sign_tropical',
            'saturn_sign_sidereal', 'saturn_sign_tropical',
        ]
        
        # Check for unwanted columns
        found_unwanted = [col for col in unwanted_columns if col in columns]
        
        if found_unwanted:
            print(f"\n⚠️  Found {len(found_unwanted)} unwanted columns (should be removed):")
            for col in found_unwanted:
                print(f"  - {col}")
            print("\n  Run: python scripts/minimize_database_columns.py to remove them")
        else:
            print("\n✓ No unwanted columns found")
        
        # Check for missing essential columns
        missing_essential = [col for col in ['planetary_placements_json', 'top_aspects_json'] if col not in columns]
        if missing_essential:
            print(f"\n⚠️  Missing essential JSON columns: {len(missing_essential)}")
            for col in missing_essential:
                print(f"  - {col}")
        
        # Check indexes
        indexes = inspector.get_indexes('famous_people')
        indexed_columns = set()
        for idx in indexes:
            indexed_columns.update(idx['column_names'])
        
        print(f"\nIndexed columns: {len(indexed_columns)}")
        print(f"  {', '.join(sorted(indexed_columns))}")
        
        # Expected indexed columns (based on current model)
        expected_indexed = {
            'id', 'name', 'sun_sign_sidereal', 'sun_sign_tropical',
            'moon_sign_sidereal', 'moon_sign_tropical',
            'life_path_number', 'chinese_zodiac_animal', 'page_views'
        }
        
        # Check if rising signs are still indexed (they shouldn't be)
        if 'rising_sign_sidereal' in indexed_columns or 'rising_sign_tropical' in indexed_columns:
            print("\n⚠️  WARNING: Rising sign columns are still indexed!")
            print("  They should not be indexed to reduce database size.")
            print("  You may need to drop these indexes manually.")
        
        # Check data population (only if columns exist)
        if not missing_columns:
            try:
                total_records = db.query(FamousPerson).count()
                print(f"\nTotal records: {total_records:,}")
                
                if total_records > 0:
                    # Check if new columns are populated
                    if 'planetary_placements_json' in columns:
                        records_with_placements = db.query(FamousPerson).filter(
                            FamousPerson.planetary_placements_json.isnot(None)
                        ).count()
                        print(f"Records with planetary_placements_json: {records_with_placements:,} ({records_with_placements/total_records*100:.1f}%)")
                    
                    if 'top_aspects_json' in columns:
                        records_with_aspects = db.query(FamousPerson).filter(
                            FamousPerson.top_aspects_json.isnot(None)
                        ).count()
                        print(f"Records with top_aspects_json: {records_with_aspects:,} ({records_with_aspects/total_records*100:.1f}%)")
                    
                    # Check a sample record
                    sample = db.query(FamousPerson).first()
                    if sample:
                        print(f"\nSample record: {sample.name}")
                        print(f"  Has chart_data_json: {bool(sample.chart_data_json)}")
                        if 'planetary_placements_json' in columns:
                            print(f"  Has planetary_placements_json: {bool(sample.planetary_placements_json)}")
                        if 'top_aspects_json' in columns:
                            print(f"  Has top_aspects_json: {bool(sample.top_aspects_json)}")
            except Exception as e:
                print(f"\n⚠️  Could not check data (columns may be missing): {e}")
        else:
            print("\n⚠️  Cannot check data - missing columns must be added first")
        
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        
        if missing_columns:
            print("❌ Database schema is NOT up to date")
            print("   Run migration script to add missing columns")
        else:
            print("✓ Database schema is up to date")
            
            if total_records > 0:
                if 'planetary_placements_json' in columns:
                    if records_with_placements < total_records:
                        print("⚠️  New columns exist but data not populated")
                        print("   Run: python scripts/calculate_all_placements.py")
                    else:
                        print("✓ All data is populated")
        
    except Exception as e:
        print(f"\n✗ Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_database_status()

