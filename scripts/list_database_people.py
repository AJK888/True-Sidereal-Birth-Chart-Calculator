"""
List all famous people currently in the database.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db

def list_people():
    """List all famous people in the database."""
    init_db()
    db = SessionLocal()
    
    try:
        people = db.query(FamousPerson).order_by(FamousPerson.name).all()
        
        print("=" * 70)
        print(f"FAMOUS PEOPLE IN DATABASE: {len(people)} total")
        print("=" * 70)
        print()
        
        if not people:
            print("No people found in database.")
            return
        
        for i, person in enumerate(people, 1):
            birth_info = f"{person.birth_year}-{person.birth_month:02d}-{person.birth_day:02d}" if person.birth_year and person.birth_month and person.birth_day else "Unknown"
            location = person.birth_location or "Unknown"
            occupation = person.occupation or "Unknown"
            
            print(f"{i:4d}. {person.name}")
            print(f"      Born: {birth_info} in {location}")
            print(f"      Occupation: {occupation}")
            
            if person.sidereal_sun_sign:
                print(f"      Signs: {person.sidereal_sun_sign} (Sidereal Sun), {person.tropical_sun_sign or 'N/A'} (Tropical Sun)")
            
            if person.life_path_number:
                print(f"      Numerology: Life Path {person.life_path_number}, Day {person.day_number or 'N/A'}")
            
            if person.chinese_zodiac_animal:
                print(f"      Chinese Zodiac: {person.chinese_zodiac_element or 'N/A'} {person.chinese_zodiac_animal}")
            
            if person.wikipedia_url:
                print(f"      Wikipedia: {person.wikipedia_url}")
            
            print()
        
        print("=" * 70)
        print(f"Total: {len(people)} people")
        print("=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    list_people()

