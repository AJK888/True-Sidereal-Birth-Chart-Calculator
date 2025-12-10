#!/usr/bin/env python3
"""Run chart calculation with verbose output."""

import os
import sys
import traceback

os.environ['OPENCAGE_KEY'] = '122d238a65bc443297d6144ba105975d'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("CHART CALCULATION SCRIPT - VERBOSE MODE")
print("=" * 70)
print(f"Python: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"OPENCAGE_KEY: {'SET' if os.getenv('OPENCAGE_KEY') else 'NOT SET'}")

try:
    print("\n1. Testing imports...")
    from database import SessionLocal, FamousPerson, init_db
    print("   ✓ Database imports OK")
    
    from natal_chart import NatalChart
    print("   ✓ NatalChart import OK")
    
    import requests
    print("   ✓ Requests import OK")
    
    import pyswisseph as swe
    print(f"   ✓ pyswisseph import OK (version: {swe.version})")
    
    print("\n2. Testing chart calculation functionality...")
    print("   Chart calculates:")
    print("   - All planets: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, True Node")
    print("   - Additional bodies: Lilith, Vertex, Ceres, Pallas, Juno, Vesta")
    print("   - Angles: Ascendant, Descendant, MC, IC")
    print("   - Aspects: Conjunction, Opposition, Trine, Square, Sextile, Quincunx, Semisextile, Semisquare, Sesquiquadrate, Quintile, Biquintile")
    print("   - Aspect patterns: T-Squares, Grand Trines, Grand Crosses, Yods, Stelliums")
    print("   - Dominance analysis: Signs, elements, modalities, planets")
    print("   - Both Sidereal AND Tropical calculations")
    print("   - When unknown_time=True: Skips houses, Part of Fortune, day/night determination")
    
    print("\n3. Running chart calculation script...")
    from scripts.calculate_famous_people_charts import process_famous_people
    process_famous_people()
    
    print("\n4. Checking database...")
    import sqlite3
    if os.path.exists('synthesis_astrology.db'):
        conn = sqlite3.connect('synthesis_astrology.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM famous_people")
        count = c.fetchone()[0]
        print(f"   ✓ Database exists with {count} records")
        
        if count > 0:
            c.execute("SELECT name, birth_year, birth_month, birth_day FROM famous_people LIMIT 5")
            records = c.fetchall()
            print("\n   Sample records:")
            for name, year, month, day in records:
                print(f"     - {name}: {month}/{day}/{year}")
        conn.close()
    else:
        print("   ✗ Database file not found")
    
    print("\n" + "=" * 70)
    print("SCRIPT COMPLETED")
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)

