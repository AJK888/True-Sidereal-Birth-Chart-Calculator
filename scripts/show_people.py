import sqlite3
import os

db_path = "synthesis_astrology.db"
if not os.path.exists(db_path):
    print(f"Database not found: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name, birth_year, birth_month, birth_day, birth_location, occupation, sidereal_sun_sign, tropical_sun_sign, life_path_number, chinese_zodiac_animal, chinese_zodiac_element FROM famous_people ORDER BY name")
rows = c.fetchall()

output_lines = []
output_lines.append("=" * 70)
output_lines.append(f"FAMOUS PEOPLE IN DATABASE: {len(rows)} total")
output_lines.append("=" * 70)
output_lines.append("")

if rows:
    for i, r in enumerate(rows, 1):
        name, year, month, day, location, occupation, sid_sun, trop_sun, life_path, chinese_animal, chinese_element = r
        birth_str = f"{year}-{month:02d}-{day:02d}" if year and month and day else "Unknown"
        location_str = location or "Unknown"
        occ_str = occupation or "Unknown"
        
        output_lines.append(f"{i}. {name}")
        output_lines.append(f"   Born: {birth_str} in {location_str}")
        output_lines.append(f"   Occupation: {occ_str}")
        
        if sid_sun or trop_sun:
            output_lines.append(f"   Signs: {sid_sun or 'N/A'} (Sidereal Sun), {trop_sun or 'N/A'} (Tropical Sun)")
        
        if life_path:
            output_lines.append(f"   Life Path Number: {life_path}")
        
        if chinese_animal:
            output_lines.append(f"   Chinese Zodiac: {chinese_element or 'N/A'} {chinese_animal}")
        
        output_lines.append("")
else:
    output_lines.append("No people found in database.")

output_lines.append("=" * 70)

output_text = "\n".join(output_lines)
print(output_text)

with open("people_list.txt", "w", encoding="utf-8") as f:
    f.write(output_text)

conn.close()

