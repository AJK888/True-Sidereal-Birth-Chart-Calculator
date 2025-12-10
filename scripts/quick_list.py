import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db

init_db()
db = SessionLocal()
people = db.query(FamousPerson).order_by(FamousPerson.name).all()

output = []
output.append("=" * 70)
output.append(f"FAMOUS PEOPLE IN DATABASE: {len(people)} total")
output.append("=" * 70)
output.append("")

if people:
    for i, person in enumerate(people, 1):
        birth_info = f"{person.birth_year}-{person.birth_month:02d}-{person.birth_day:02d}" if person.birth_year and person.birth_month and person.birth_day else "Unknown"
        location = person.birth_location or "Unknown"
        occupation = person.occupation or "Unknown"
        
        output.append(f"{i}. {person.name}")
        output.append(f"   Born: {birth_info} in {location}")
        output.append(f"   Occupation: {occupation}")
        if person.sidereal_sun_sign:
            output.append(f"   Signs: {person.sidereal_sun_sign} (Sidereal), {person.tropical_sun_sign or 'N/A'} (Tropical)")
        if person.life_path_number:
            output.append(f"   Numerology: Life Path {person.life_path_number}")
        if person.chinese_zodiac_animal:
            output.append(f"   Chinese Zodiac: {person.chinese_zodiac_element or 'N/A'} {person.chinese_zodiac_animal}")
        output.append("")
else:
    output.append("No people found in database.")

output.append("=" * 70)

with open("database_people_list.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("\n".join(output))
db.close()

