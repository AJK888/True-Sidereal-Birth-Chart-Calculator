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
            # Get names
            c.execute("SELECT name, birth_year, birth_month, birth_day FROM famous_people LIMIT 10")
            records = c.fetchall()
            print("\nSample records:")
            for name, year, month, day in records:
                print(f"  - {name}: {month}/{day}/{year}")
        else:
            print("  No records found in database")
    else:
        print("✗ 'famous_people' table does not exist")
    
    conn.close()
else:
    print(f"✗ Database file does not exist: {db_path}")
    print("  The script may not have run yet, or there was an error.")

print("=" * 60)

