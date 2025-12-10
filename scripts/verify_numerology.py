#!/usr/bin/env python3
"""Verify that numerology and Chinese zodiac were calculated and stored."""

import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("VERIFYING NUMEROLOGY AND CHINESE ZODIAC IN DATABASE")
print("=" * 70)

db_path = "synthesis_astrology.db"

if not os.path.exists(db_path):
    print(f"\n✗ Database file '{db_path}' not found.")
    print("  Run: python scripts/calculate_famous_people_charts.py")
    sys.exit(1)

print(f"\n✓ Database file found: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Check if table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='famous_people'")
    if not c.fetchone():
        print("\n✗ Table 'famous_people' does not exist.")
        print("  Run: python scripts/calculate_famous_people_charts.py")
        conn.close()
        sys.exit(1)
    
    print("✓ Table 'famous_people' exists")
    
    # Check columns
    c.execute("PRAGMA table_info(famous_people)")
    columns = [col[1] for col in c.fetchall()]
    print(f"\nColumns in table: {len(columns)}")
    
    required_cols = ['life_path_number', 'day_number', 'chinese_zodiac_animal', 'chinese_zodiac_element']
    missing_cols = [col for col in required_cols if col not in columns]
    
    if missing_cols:
        print(f"\n✗ Missing columns: {missing_cols}")
        print("  Run the migration: sqlite3 synthesis_astrology.db < migrate_add_numerology_chinese.sql")
        print("  Or delete the database and let it recreate with new schema")
    else:
        print("✓ All required columns exist")
    
    # Check record count
    c.execute("SELECT COUNT(*) FROM famous_people")
    count = c.fetchone()[0]
    print(f"\nTotal records: {count}")
    
    if count == 0:
        print("\n⚠ No records found. Run: python scripts/calculate_famous_people_charts.py")
    else:
        # Show sample records with numerology
        c.execute("""
            SELECT name, life_path_number, day_number, 
                   chinese_zodiac_animal, chinese_zodiac_element 
            FROM famous_people 
            LIMIT 5
        """)
        rows = c.fetchall()
        
        print("\n" + "=" * 70)
        print("SAMPLE RECORDS WITH NUMEROLOGY AND CHINESE ZODIAC:")
        print("=" * 70)
        for row in rows:
            name, lp, day, animal, element = row
            print(f"\n{name}:")
            print(f"  Life Path Number: {lp or 'NULL'}")
            print(f"  Day Number: {day or 'NULL'}")
            print(f"  Chinese Zodiac: {element or 'NULL'} {animal or 'NULL'}")
        
        # Count how many have numerology
        c.execute("SELECT COUNT(*) FROM famous_people WHERE life_path_number IS NOT NULL")
        with_num = c.fetchone()[0]
        print(f"\n{'='*70}")
        print(f"Records with numerology: {with_num} / {count}")
        
        c.execute("SELECT COUNT(*) FROM famous_people WHERE chinese_zodiac_animal IS NOT NULL")
        with_cz = c.fetchone()[0]
        print(f"Records with Chinese zodiac: {with_cz} / {count}")
    
    conn.close()
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

