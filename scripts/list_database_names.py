"""
List all names in the famous_people database.
"""
import os
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "synthesis_astrology.db"

if not DB_PATH.exists():
    print(f"Database not found: {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get count
c.execute("SELECT COUNT(*) FROM famous_people")
count = c.fetchone()[0]

print("=" * 70)
print(f"FAMOUS PEOPLE IN DATABASE: {count} total")
print("=" * 70)
print()

# Get all names with basic info
c.execute("""
    SELECT name, birth_year, birth_month, birth_day, birth_location, 
           sidereal_sun_sign, tropical_sun_sign, life_path_number
    FROM famous_people 
    ORDER BY name
""")
rows = c.fetchall()

output_lines = []
output_lines.append(f"Total: {count} people\n")

if rows:
    for i, (name, year, month, day, location, sid_sun, trop_sun, life_path) in enumerate(rows, 1):
        birth_str = f"{year}-{month:02d}-{day:02d}" if year and month and day else "Unknown"
        location_str = (location or "Unknown")[:50]  # Truncate long locations
        signs = f"{sid_sun or 'N/A'}/{trop_sun or 'N/A'}"
        life_path_str = f"LP:{life_path}" if life_path else ""
        
        line = f"{i:4d}. {name:<40} {birth_str:12} {signs:15} {life_path_str}"
        output_lines.append(line)
        
        # Print every 100 to show progress
        if i % 100 == 0:
            print(f"Processed {i}/{count}...")
else:
    output_lines.append("No people found in database.")

# Write to file
output_file = BASE_DIR / "database_names_list.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

# Also print summary
print("\n" + "=" * 70)
print(f"List saved to: {output_file}")
print("=" * 70)
print(f"\nFirst 20 names:")
for line in output_lines[1:21]:  # Skip header, show first 20
    print(line)

if count > 20:
    print(f"\n... and {count - 20} more (see {output_file} for full list)")

conn.close()

