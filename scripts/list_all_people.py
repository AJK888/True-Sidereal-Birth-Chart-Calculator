#!/usr/bin/env python3
"""List all famous people in the database."""

import sqlite3
import os
import sys

# Change to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(script_dir))

db_path = "synthesis_astrology.db"
output_file = "database_people_list.txt"

if not os.path.exists(db_path):
    with open(output_file, "w") as f:
        f.write(f"ERROR: Database file not found: {db_path}\n")
        f.write("The database may be on a remote server (Render) or not created yet.\n")
    print(f"ERROR: Database file not found: {db_path}")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get all people
    c.execute("""
        SELECT name, birth_year, birth_month, birth_day, birth_location, 
               occupation, sidereal_sun_sign, tropical_sun_sign, 
               life_path_number, day_number, chinese_zodiac_animal, chinese_zodiac_element
        FROM famous_people 
        ORDER BY name
    """)
    rows = c.fetchall()
    
    # Write to file and print
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write(f"FAMOUS PEOPLE IN DATABASE: {len(rows)} total\n")
        f.write("=" * 70 + "\n\n")
        
        if rows:
            for i, r in enumerate(rows, 1):
                name, year, month, day, location, occupation, sid_sun, trop_sun, life_path, day_num, chinese_animal, chinese_element = r
                
                birth_str = f"{year}-{month:02d}-{day:02d}" if year and month and day else "Unknown"
                location_str = location or "Unknown"
                occ_str = occupation or "Unknown"
                
                line = f"{i}. {name}\n"
                line += f"   Born: {birth_str} in {location_str}\n"
                line += f"   Occupation: {occ_str}\n"
                
                if sid_sun or trop_sun:
                    line += f"   Signs: {sid_sun or 'N/A'} (Sidereal Sun), {trop_sun or 'N/A'} (Tropical Sun)\n"
                
                if life_path:
                    line += f"   Numerology: Life Path {life_path}"
                    if day_num:
                        line += f", Day {day_num}"
                    line += "\n"
                
                if chinese_animal:
                    line += f"   Chinese Zodiac: {chinese_element or 'N/A'} {chinese_animal}\n"
                
                line += "\n"
                f.write(line)
                print(line, end="")
        else:
            f.write("No people found in database.\n")
            print("No people found in database.")
        
        f.write("=" * 70 + "\n")
        print("=" * 70)
    
    conn.close()
    print(f"\nOutput also saved to: {output_file}")
    
except Exception as e:
    error_msg = f"ERROR: {e}\n"
    with open(output_file, "w") as f:
        f.write(error_msg)
    print(error_msg)
    import traceback
    traceback.print_exc()
    sys.exit(1)

