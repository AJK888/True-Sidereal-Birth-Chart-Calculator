"""
Update existing famous people in the database with asteroid calculations.
This script recalculates charts for people who are already in the database
to add missing asteroid data (Ceres, Pallas, Juno, Vesta, Chiron).
"""
import os
import sys
import json
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db
from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
if not OPENCAGE_KEY:
    logger.error("OPENCAGE_KEY not set. Set it with: export OPENCAGE_KEY='your_key'")
    sys.exit(1)

def geocode_location(location: str):
    """Geocode location using OpenCage API."""
    import requests
    import time
    
    try:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            "q": location,
            "key": OPENCAGE_KEY,
            "limit": 1
        }
        headers = {"User-Agent": "SynthesisAstrology/1.0"}
        
        time.sleep(0.1)  # Rate limiting
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get("results"):
            result = data["results"][0]
            geometry = result.get("geometry", {})
            components = result.get("components", {})
            
            return {
                "latitude": geometry.get("lat"),
                "longitude": geometry.get("lng"),
                "timezone": components.get("timezone") or "UTC"
            }
    except Exception as e:
        logger.warning(f"Geocoding failed for {location}: {e}")
    
    return None

def update_person_chart(person: FamousPerson):
    """Recalculate and update chart for an existing person."""
    if not person.birth_year or not person.birth_month or not person.birth_day:
        logger.warning(f"Skipping {person.name}: Missing birth date")
        return False
    
    if not person.birth_location:
        logger.warning(f"Skipping {person.name}: Missing birth location")
        return False
    
    # Geocode location
    geo = geocode_location(person.birth_location)
    if not geo:
        logger.warning(f"Could not geocode: {person.birth_location} for {person.name}")
        return False
    
    # Default to noon if time unknown
    hour = person.birth_hour if person.birth_hour is not None else 12
    minute = person.birth_minute if person.birth_minute is not None else 0
    unknown_time = person.unknown_time if person.unknown_time is not None else True
    
    try:
        chart = NatalChart(
            name=person.name,
            year=person.birth_year,
            month=person.birth_month,
            day=person.birth_day,
            hour=hour,
            minute=minute,
            latitude=geo["latitude"],
            longitude=geo["longitude"]
        )
        
        chart.calculate_chart(unknown_time=unknown_time)
        
        # Calculate numerology
        numerology_data = calculate_numerology(
            person.birth_day,
            person.birth_month,
            person.birth_year
        )
        
        # Calculate Chinese zodiac
        chinese_zodiac = get_chinese_zodiac_and_element(
            person.birth_year,
            person.birth_month,
            person.birth_day
        )
        
        # Get full chart data (with asteroids)
        chart_data = chart.get_full_chart_data(
            numerology_data,
            None,  # name_numerology
            chinese_zodiac,
            unknown_time
        )
        
        # Extract key elements
        elements = {}
        for body in chart.celestial_bodies:
            if body.name == "Sun":
                elements["sun_sign_sidereal"] = body.sign
            elif body.name == "Moon":
                elements["moon_sign_sidereal"] = body.sign
            elif body.name == "Ascendant":
                elements["rising_sign_sidereal"] = body.sign
        
        for body in chart.tropical_bodies:
            if body.name == "Sun":
                elements["sun_sign_tropical"] = body.sign
            elif body.name == "Moon":
                elements["moon_sign_tropical"] = body.sign
            elif body.name == "Ascendant":
                elements["rising_sign_tropical"] = body.sign
        
        # Parse Chinese zodiac
        chinese_animal = None
        chinese_element = None
        if chinese_zodiac and isinstance(chinese_zodiac, str) and chinese_zodiac != 'N/A':
            parts = chinese_zodiac.strip().split()
            if len(parts) >= 2:
                chinese_element = parts[0]
                chinese_animal = parts[1]
        
        # Update database entry
        person.chart_data_json = json.dumps(chart_data)
        person.sun_sign_sidereal = elements.get("sun_sign_sidereal")
        person.sun_sign_tropical = elements.get("sun_sign_tropical")
        person.moon_sign_sidereal = elements.get("moon_sign_sidereal")
        person.moon_sign_tropical = elements.get("moon_sign_tropical")
        person.rising_sign_sidereal = elements.get("rising_sign_sidereal")
        person.rising_sign_tropical = elements.get("rising_sign_tropical")
        person.life_path_number = numerology_data.get("life_path_number")
        person.day_number = numerology_data.get("day_number")
        person.chinese_zodiac_animal = chinese_animal
        person.chinese_zodiac_element = chinese_element
        
        return True
        
    except Exception as e:
        logger.error(f"Chart calculation error for {person.name}: {e}")
        return False

def main():
    """Update all existing people with asteroid calculations."""
    output_file = open("update_asteroids_output.txt", "w", encoding="utf-8")
    
    def log_print(msg):
        print(msg)
        output_file.write(str(msg) + "\n")
        output_file.flush()
    
    log_print("=" * 70)
    log_print("UPDATE EXISTING PEOPLE WITH ASTEROIDS")
    log_print("=" * 70)
    log_print(f"Started: {datetime.now()}")
    log_print(f"OPENCAGE_KEY: {'SET' if OPENCAGE_KEY else 'NOT SET'}")
    log_print("=" * 70)
    
    init_db()
    db = SessionLocal()
    
    try:
        # Get all people from database
        all_people = db.query(FamousPerson).all()
        log_print(f"\nFound {len(all_people)} people in database")
        log_print("Updating charts with asteroid calculations...")
        log_print()
        
        updated = 0
        failed = 0
        skipped = 0
        
        for idx, person in enumerate(all_people, 1):
            if update_person_chart(person):
                updated += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(all_people)} (updated: {updated}, failed: {failed}, skipped: {skipped})")
            else:
                failed += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(all_people)} (updated: {updated}, failed: {failed}, skipped: {skipped})")
            
            # Commit every 50 people
            if idx % 50 == 0:
                try:
                    db.commit()
                    log_print(f"   ✓ Committed batch: {idx} people updated")
                except Exception as e:
                    log_print(f"   ✗ Error committing batch: {e}")
                    db.rollback()
        
        # Final commit
        try:
            db.commit()
            log_print(f"\n   ✓ Final commit: All updates saved")
        except Exception as e:
            log_print(f"\n   ✗ Error in final commit: {e}")
            db.rollback()
        
        log_print("\n" + "=" * 70)
        log_print("UPDATE COMPLETE!")
        log_print("=" * 70)
        log_print(f"Total people: {len(all_people)}")
        log_print(f"Updated: {updated}")
        log_print(f"Failed: {failed}")
        log_print(f"Skipped: {skipped}")
        log_print(f"Finished: {datetime.now()}")
        log_print("=" * 70)
    
    except Exception as e:
        log_print(f"\nERROR: {e}")
        import traceback
        log_print(traceback.format_exc())
        db.rollback()
    finally:
        db.close()
        output_file.close()

if __name__ == "__main__":
    main()

