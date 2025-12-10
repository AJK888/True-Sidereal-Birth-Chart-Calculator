"""
Calculate birth charts for famous people and store in database.

Usage:
    python scripts/calculate_famous_people_charts.py

This script:
1. Reads famous people data from JSON file
2. Calculates their birth charts using the chart calculator
3. Stores results in the database
"""

import os
import sys
import json
import logging
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db
from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
if not OPENCAGE_KEY:
    logger.warning("OPENCAGE_KEY environment variable not set. Geocoding will be skipped for locations that need it.")
    logger.warning("Some historical locations may not geocode correctly without an API key.")


def geocode_location(location: str) -> Optional[Dict]:
    """Geocode location using OpenCage API."""
    if not OPENCAGE_KEY:
        logger.warning(f"Cannot geocode {location}: OPENCAGE_KEY not set")
        return None
    
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q={location}&key={OPENCAGE_KEY}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if results:
            result = results[0]
            geometry = result.get("geometry", {})
            annotations = result.get("annotations", {}).get("timezone", {})
            return {
                "lat": geometry.get("lat"),
                "lng": geometry.get("lng"),
                "timezone": annotations.get("name")
            }
    except Exception as e:
        logger.error(f"Error geocoding {location}: {e}")
    return None


def extract_chart_elements(chart_data: Dict) -> Dict:
    """Extract key chart elements for similarity matching."""
    elements = {}
    
    # Extract Sun, Moon, Rising from sidereal
    s_positions = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
    s_extra = {p['name']: p for p in chart_data.get('sidereal_additional_points', [])}
    
    if 'Sun' in s_positions:
        sun_pos = s_positions['Sun'].get('position', '')
        elements['sun_sign_sidereal'] = sun_pos.split()[-1] if sun_pos else None
    
    if 'Moon' in s_positions:
        moon_pos = s_positions['Moon'].get('position', '')
        elements['moon_sign_sidereal'] = moon_pos.split()[-1] if moon_pos else None
    
    if 'Ascendant' in s_extra:
        asc_info = s_extra['Ascendant'].get('info', '')
        elements['rising_sign_sidereal'] = asc_info.split()[0] if asc_info else None
    
    # Extract from tropical
    t_positions = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
    t_extra = {p['name']: p for p in chart_data.get('tropical_additional_points', [])}
    
    if 'Sun' in t_positions:
        sun_pos = t_positions['Sun'].get('position', '')
        elements['sun_sign_tropical'] = sun_pos.split()[-1] if sun_pos else None
    
    if 'Moon' in t_positions:
        moon_pos = t_positions['Moon'].get('position', '')
        elements['moon_sign_tropical'] = moon_pos.split()[-1] if moon_pos else None
    
    if 'Ascendant' in t_extra:
        asc_info = t_extra['Ascendant'].get('info', '')
        elements['rising_sign_tropical'] = asc_info.split()[0] if asc_info else None
    
    return elements


def calculate_person_chart(person_data: Dict) -> Optional[Dict]:
    """Calculate birth chart for a famous person."""
    try:
        birth_date = person_data.get('birth_date', {})
        if not birth_date:
            logger.warning(f"No birth date for {person_data.get('name')}")
            return None
        
        year = birth_date.get('year')
        month = birth_date.get('month')
        day = birth_date.get('day')
        hour = birth_date.get('hour', 12)  # Default to noon if unknown
        minute = birth_date.get('minute', 0)
        unknown_time = birth_date.get('hour') is None
        
        location = person_data.get('birth_location')
        if not location:
            logger.warning(f"No birth location for {person_data.get('name')} - skipping")
            return None
        
        # Geocode location
        geo = geocode_location(location)
        if not geo:
            logger.warning(f"Could not geocode {location} for {person_data.get('name')}")
            return None
        
        # Calculate chart
        chart = NatalChart(
            name=person_data.get('name', 'Unknown'),
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            latitude=geo['lat'],
            longitude=geo['lng']
        )
        chart.calculate_chart(unknown_time=unknown_time)
        
        # Calculate numerology (life path and day number only)
        numerology_raw = calculate_numerology(day, month, year)
        numerology = {
            "life_path_number": numerology_raw.get("life_path", "N/A"),
            "day_number": numerology_raw.get("day_number", "N/A"),
            "lucky_number": numerology_raw.get("lucky_number", "N/A")
        }
        
        # Calculate Chinese zodiac
        chinese_zodiac = get_chinese_zodiac_and_element(year, month, day)
        
        # Get full chart data
        chart_data = chart.get_full_chart_data(
            numerology=numerology,
            name_numerology=None,  # Not calculating name numerology for famous people
            chinese_zodiac=chinese_zodiac,
            unknown_time=unknown_time
        )
        
        # Extract key elements
        elements = extract_chart_elements(chart_data)
        
        return {
            'chart_data': chart_data,
            'elements': elements,
            'unknown_time': unknown_time
        }
    except Exception as e:
        logger.error(f"Error calculating chart for {person_data.get('name')}: {e}", exc_info=True)
        return None


def process_famous_people(input_file: str = "famous_people_data.json"):
    """Process famous people data and calculate charts."""
    output_file = open("chart_calc_output.txt", "w", encoding="utf-8")
    def log_print(msg):
        print(msg)
        output_file.write(str(msg) + "\n")
        output_file.flush()
    
    log_print(f"Starting process_famous_people with input file: {input_file}")
    # Initialize database
    log_print("Initializing database...")
    init_db()
    log_print("Creating database session...")
    db = SessionLocal()
    
    try:
        # Load data
        if not os.path.exists(input_file):
            log_print(f"ERROR: Input file {input_file} not found. Run scrape_wikipedia_famous_people.py first.")
            output_file.close()
            return
        
        with open(input_file, 'r', encoding='utf-8') as f:
            people_data = json.load(f)
        
        log_print(f"Processing {len(people_data)} famous people...")
        
        processed = 0
        skipped = 0
        errors = 0
        
        for person_data in people_data:
            name = person_data.get('name')
            if not name:
                skipped += 1
                continue
            
            # Check if already exists
            existing = db.query(FamousPerson).filter(FamousPerson.name == name).first()
            if existing:
                log_print(f"Already exists: {name}")
                skipped += 1
                continue
            
            log_print(f"\n[{processed + skipped + errors + 1}/{len(people_data)}] Processing: {name}")
            # Calculate chart
            chart_result = calculate_person_chart(person_data)
            if not chart_result:
                log_print(f"  ✗ Failed to calculate chart")
                errors += 1
                continue
            
            log_print(f"  ✓ Chart calculated successfully")
            
            # Create database entry
            birth_date = person_data.get('birth_date', {})
            
            # Extract numerology and Chinese zodiac from chart data
            numerology_data = chart_result['chart_data'].get('numerology_analysis', {})
            chinese_zodiac_str = chart_result['chart_data'].get('chinese_zodiac', '')
            
            # Parse Chinese zodiac string (format: "Metal Pig" or "Wood Rat")
            chinese_animal = None
            chinese_element = None
            if chinese_zodiac_str and isinstance(chinese_zodiac_str, str) and chinese_zodiac_str != 'N/A':
                parts = chinese_zodiac_str.strip().split()
                if len(parts) >= 2:
                    chinese_element = parts[0]
                    chinese_animal = parts[1]
                elif len(parts) == 1:
                    # Sometimes it might just be the animal
                    chinese_animal = parts[0]
            
            famous_person = FamousPerson(
                name=name,
                wikipedia_url=person_data.get('wikipedia_url', ''),
                occupation=person_data.get('occupation'),
                birth_year=birth_date.get('year'),
                birth_month=birth_date.get('month'),
                birth_day=birth_date.get('day'),
                birth_hour=birth_date.get('hour'),
                birth_minute=birth_date.get('minute'),
                birth_location=person_data.get('birth_location', ''),
                unknown_time=chart_result['unknown_time'],
                chart_data_json=json.dumps(chart_result['chart_data']),
                sun_sign_sidereal=chart_result['elements'].get('sun_sign_sidereal'),
                sun_sign_tropical=chart_result['elements'].get('sun_sign_tropical'),
                moon_sign_sidereal=chart_result['elements'].get('moon_sign_sidereal'),
                moon_sign_tropical=chart_result['elements'].get('moon_sign_tropical'),
                rising_sign_sidereal=chart_result['elements'].get('rising_sign_sidereal'),
                rising_sign_tropical=chart_result['elements'].get('rising_sign_tropical'),
                life_path_number=numerology_data.get('life_path_number'),
                day_number=numerology_data.get('day_number'),
                chinese_zodiac_animal=chinese_animal,
                chinese_zodiac_element=chinese_element,
            )
            
            db.add(famous_person)
            processed += 1
            
            if processed % 10 == 0:
                db.commit()
                log_print(f"Committed {processed} people to database...")
        
        db.commit()
        log_print(f"\n{'='*60}")
        log_print(f"Complete! Processed: {processed}, Skipped: {skipped}, Errors: {errors}")
        log_print(f"{'='*60}")
    
    except Exception as e:
        log_print(f"ERROR: {e}")
        import traceback
        log_print(traceback.format_exc())
        db.rollback()
    finally:
        db.close()
        output_file.close()


if __name__ == "__main__":
    print("Starting chart calculation script...")
    print(f"OPENCAGE_KEY: {'SET' if OPENCAGE_KEY else 'NOT SET'}")
    process_famous_people()
    print("Script completed.")

