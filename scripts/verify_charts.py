#!/usr/bin/env python3
"""Verify if charts were calculated and stored."""

import os
import sys
import sqlite3

os.environ['OPENCAGE_KEY'] = '122d238a65bc443297d6144ba105975d'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("Verifying Chart Calculation")
print("=" * 60)

# Check if database exists
db_path = "synthesis_astrology.db"
if os.path.exists(db_path):
    print(f"✓ Database file exists: {db_path}")
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check if table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='famous_people'")
    if c.fetchone():
        print("✓ 'famous_people' table exists")
        
        # Count records
        c.execute("SELECT COUNT(*) FROM famous_people")
        count = c.fetchone()[0]
        print(f"✓ Records in database: {count}")
        
        if count > 0:
            # Get all people with full details
            c.execute("""
                SELECT name, birth_year, birth_month, birth_day, birth_location, 
                       occupation, sidereal_sun_sign, tropical_sun_sign, 
                       life_path_number, chinese_zodiac_animal, chinese_zodiac_element
                FROM famous_people 
                ORDER BY name
            """)
            records = c.fetchall()
            print("\nAll people in database:")
            print("=" * 70)
            for i, (name, year, month, day, location, occupation, sid_sun, trop_sun, life_path, chinese_animal, chinese_element) in enumerate(records, 1):
                birth_str = f"{year}-{month:02d}-{day:02d}" if year and month and day else "Unknown"
                location_str = location or "Unknown"
                occ_str = occupation or "Unknown"
                
                print(f"\n{i}. {name}")
                print(f"   Born: {birth_str} in {location_str}")
                print(f"   Occupation: {occ_str}")
                if sid_sun or trop_sun:
                    print(f"   Signs: {sid_sun or 'N/A'} (Sidereal), {trop_sun or 'N/A'} (Tropical)")
                if life_path:
                    print(f"   Life Path: {life_path}")
                if chinese_animal:
                    print(f"   Chinese Zodiac: {chinese_element or 'N/A'} {chinese_animal}")
        else:
            print("  No records found in database")
    else:
        print("✗ 'famous_people' table does not exist")
    
    conn.close()
else:
    print(f"✗ Database file does not exist: {db_path}")
    print("  The script may not have run yet, or there was an error.")

print("=" * 60)

