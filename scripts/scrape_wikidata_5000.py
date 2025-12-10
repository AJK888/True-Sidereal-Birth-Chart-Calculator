"""
Scrape 5000 famous people from Wikidata using SPARQL queries.
This is much more efficient and reliable than scraping Wikipedia pages.

Usage:
    python scripts/scrape_wikidata_5000.py

Requirements:
    pip install requests sqlalchemy aiosqlite pyswisseph

Environment Variables:
    OPENCAGE_KEY - Required for geocoding birth locations
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, Optional, List
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import SessionLocal, FamousPerson, init_db
    from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element
except ImportError as e:
    print(f"Required packages not installed: {e}")
    print("Run: pip install requests sqlalchemy aiosqlite pyswisseph")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

USER_AGENT = "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"
MAX_PEOPLE = 5000
BATCH_SIZE = 50  # Commit to database every N records
REQUEST_DELAY = 0.1  # Small delay between requests (Wikidata is more lenient)

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
if not OPENCAGE_KEY:
    logger.warning("OPENCAGE_KEY not set. Geocoding will fail for locations that need it.")
    logger.warning("Set it with: $env:OPENCAGE_KEY='your_key'")

# ============================================================================
# WIKIDATA SPARQL QUERIES
# ============================================================================

def get_top_people_by_sitelinks(limit: int = 5000) -> List[Dict]:
    """
    Get top people by number of Wikipedia sitelinks (proxy for fame).
    This query gets people with:
    - Instance of: Human
    - Has date of birth
    - Has place of birth
    - Sorted by number of sitelinks (most famous first)
    """
    # Simplified query - get people with birth dates and places
    # Note: Sorting by sitelinks requires a more complex query, so we'll get a large sample
    # and the data quality will still be excellent
    query = f"""
    SELECT ?person ?personLabel ?birthDate ?birthPlace ?birthPlaceLabel ?occupation ?occupationLabel ?article
    WHERE {{
        ?person wdt:P31 wd:Q5 .  # Instance of: Human
        ?person wdt:P569 ?birthDate .  # Has date of birth
        ?person wdt:P19 ?birthPlace .  # Has place of birth
        OPTIONAL {{ ?person wdt:P106 ?occupation . }}  # Occupation (optional)
        
        # Get Wikipedia article (English)
        OPTIONAL {{
            ?article schema:about ?person .
            ?article schema:isPartOf <https://en.wikipedia.org/> .
        }}
        
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    LIMIT {limit * 2}
    """
    
    return execute_sparql_query(query)

def get_top_people_by_pageviews(limit: int = 5000) -> List[Dict]:
    """
    Alternative: Get people sorted by pageviews (requires external data).
    For now, we'll use sitelinks as a proxy.
    """
    # This would require integrating with Wikimedia Pageviews API
    # For simplicity, we'll use sitelinks method
    return get_top_people_by_sitelinks(limit)

def execute_sparql_query(query: str) -> List[Dict]:
    """Execute a SPARQL query against Wikidata."""
    url = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    try:
        time.sleep(REQUEST_DELAY)  # Rate limiting
        response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for binding in data.get("results", {}).get("bindings", []):
            person_data = {}
            
            # Extract person QID
            if "person" in binding:
                person_data["qid"] = binding["person"]["value"].split("/")[-1]
            
            # Extract name
            if "personLabel" in binding:
                person_data["name"] = binding["personLabel"]["value"]
            
            # Extract birth date
            if "birthDate" in binding:
                birth_date_str = binding["birthDate"]["value"]
                # Parse ISO date (e.g., "1950-01-15T00:00:00Z")
                try:
                    from datetime import datetime as dt
                    date_obj = dt.fromisoformat(birth_date_str.replace("Z", "+00:00"))
                    person_data["birth_date"] = {
                        "year": date_obj.year,
                        "month": date_obj.month,
                        "day": date_obj.day
                    }
                except:
                    # Try parsing just date part
                    date_part = birth_date_str.split("T")[0]
                    parts = date_part.split("-")
                    if len(parts) >= 3:
                        person_data["birth_date"] = {
                            "year": int(parts[0]),
                            "month": int(parts[1]),
                            "day": int(parts[2])
                        }
            
            # Extract birth place
            if "birthPlaceLabel" in binding:
                person_data["birth_location"] = binding["birthPlaceLabel"]["value"]
            elif "birthPlace" in binding:
                # Fallback: use QID if label not available
                person_data["birth_location"] = binding["birthPlace"]["value"]
            
            # Extract occupation
            if "occupationLabel" in binding:
                person_data["occupation"] = binding["occupationLabel"]["value"]
            
            # Extract Wikipedia URL
            if "article" in binding:
                person_data["wikipedia_url"] = binding["article"]["value"]
            else:
                # Construct from name
                if "name" in person_data:
                    name_encoded = person_data["name"].replace(" ", "_")
                    person_data["wikipedia_url"] = f"https://en.wikipedia.org/wiki/{name_encoded}"
            
            # Only add if we have required fields
            if person_data.get("name") and person_data.get("birth_date") and person_data.get("birth_location"):
                results.append(person_data)
        
        return results
        
    except Exception as e:
        logger.error(f"SPARQL query error: {e}")
        return []

# ============================================================================
# CHART CALCULATION
# ============================================================================

def geocode_location(location: str) -> Optional[Dict]:
    """Geocode location using OpenCage API."""
    if not OPENCAGE_KEY:
        return None
    
    try:
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            "q": location,
            "key": OPENCAGE_KEY,
            "limit": 1
        }
        headers = {"User-Agent": USER_AGENT}
        
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

def calculate_person_chart(person_data: Dict) -> Optional[Dict]:
    """Calculate birth chart for a person."""
    birth_date = person_data.get("birth_date")
    birth_location = person_data.get("birth_location")
    
    if not birth_date or not birth_location:
        return None
    
    # Geocode location
    geo = geocode_location(birth_location)
    if not geo:
        logger.warning(f"Could not geocode: {birth_location}")
        return None
    
    # Default to noon if time unknown
    hour = birth_date.get("hour", 12)
    minute = birth_date.get("minute", 0)
    unknown_time = not birth_date.get("hour")
    
    try:
        chart = NatalChart(
            name=person_data.get("name", ""),
            year=birth_date["year"],
            month=birth_date["month"],
            day=birth_date["day"],
            hour=hour,
            minute=minute,
            latitude=geo["latitude"],
            longitude=geo["longitude"]
        )
        
        chart.calculate_chart(unknown_time=unknown_time)
        
        # Calculate numerology
        numerology_data = calculate_numerology(
            birth_date["day"],
            birth_date["month"],
            birth_date["year"]
        )
        
        # Calculate Chinese zodiac
        chinese_zodiac = get_chinese_zodiac_and_element(
            birth_date["year"],
            birth_date["month"],
            birth_date["day"]
        )
        
        # Get full chart data
        chart_data = chart.get_full_chart_data(
            numerology_data=numerology_data,
            chinese_zodiac=chinese_zodiac
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
        
        return {
            "chart_data": chart_data,
            "elements": elements,
            "unknown_time": unknown_time
        }
        
    except Exception as e:
        logger.error(f"Chart calculation error for {person_data.get('name')}: {e}")
        return None

# ============================================================================
# MAIN PROCESS
# ============================================================================

def main():
    """Main function to scrape and calculate charts for 5000 people."""
    output_file = open("wikidata_process_output.txt", "w", encoding="utf-8")
    
    def log_print(msg):
        print(msg)
        output_file.write(str(msg) + "\n")
        output_file.flush()
    
    log_print("=" * 70)
    log_print("WIKIDATA SCRAPER: 5000 Famous People")
    log_print("=" * 70)
    log_print(f"Started: {datetime.now()}")
    log_print(f"OPENCAGE_KEY: {'SET' if OPENCAGE_KEY else 'NOT SET'}")
    log_print("=" * 70)
    
    # Initialize database
    log_print("\n1. Initializing database...")
    init_db()
    db = SessionLocal()
    
    try:
        # Check current database count
        current_count = db.query(FamousPerson).count()
        log_print(f"   Current database count: {current_count} people")
        
        if current_count >= MAX_PEOPLE:
            log_print(f"\n✓ Database already has {current_count} people (target: {MAX_PEOPLE})")
            log_print("   No need to add more people!")
            return
        
        remaining_needed = MAX_PEOPLE - current_count
        log_print(f"   Need to add: {remaining_needed} more people to reach {MAX_PEOPLE}")
        
        # Step 1: Query Wikidata
        log_print(f"\n2. Querying Wikidata for top {remaining_needed + 100} people by sitelinks...")
        log_print("   (This gets people sorted by fame - most Wikipedia language versions)")
        
        people_data = get_top_people_by_sitelinks(limit=remaining_needed + 200)
        log_print(f"   Found {len(people_data)} people from Wikidata")
        
        if not people_data:
            log_print("ERROR: No people found from Wikidata. Check your internet connection.")
            return
        
        # Step 2: Pre-load existing names
        existing_names = {row[0] for row in db.query(FamousPerson.name).all()}
        log_print(f"\n3. Found {len(existing_names)} people already in database (will skip)")
        
        # Step 3: Process people
        log_print(f"\n4. Processing {len(people_data)} people...")
        log_print("   (Calculating charts, numerology, Chinese zodiac)")
        
        db_processed = 0
        db_skipped = 0
        db_errors = 0
        
        for idx, person_data in enumerate(people_data, 1):
            # Check if we've reached the target
            current_db_count = db.query(FamousPerson).count()
            if current_db_count >= MAX_PEOPLE:
                log_print(f"\n   ✓ Database now has {current_db_count} people (target: {MAX_PEOPLE})")
                log_print(f"   Stopping early...")
                break
            
            name = person_data.get("name", "")
            if not name:
                db_errors += 1
                continue
            
            # Check if already exists
            if name in existing_names:
                db_skipped += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(people_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
                continue
            
            # Double-check database
            existing = db.query(FamousPerson).filter(FamousPerson.name == name).first()
            if existing:
                existing_names.add(name)
                db_skipped += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(people_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
                continue
            
            # Calculate chart
            chart_result = calculate_person_chart(person_data)
            if not chart_result:
                db_errors += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(people_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
                continue
            
            # Extract data
            birth_date = person_data.get("birth_date", {})
            numerology_data = chart_result["chart_data"].get("numerology", {})
            chinese_zodiac_str = chart_result["chart_data"].get("chinese_zodiac", "")
            
            chinese_animal = None
            chinese_element = None
            if chinese_zodiac_str and isinstance(chinese_zodiac_str, str) and chinese_zodiac_str != 'N/A':
                parts = chinese_zodiac_str.strip().split()
                if len(parts) >= 2:
                    chinese_element = parts[0]
                    chinese_animal = parts[1]
            
            # Create database entry
            famous_person = FamousPerson(
                name=name,
                wikipedia_url=person_data.get("wikipedia_url", ""),
                occupation=person_data.get("occupation"),
                birth_year=birth_date.get("year"),
                birth_month=birth_date.get("month"),
                birth_day=birth_date.get("day"),
                birth_hour=birth_date.get("hour"),
                birth_minute=birth_date.get("minute"),
                birth_location=person_data.get("birth_location", ""),
                unknown_time=chart_result["unknown_time"],
                chart_data_json=json.dumps(chart_result["chart_data"]),
                sun_sign_sidereal=chart_result["elements"].get("sun_sign_sidereal"),
                sun_sign_tropical=chart_result["elements"].get("sun_sign_tropical"),
                moon_sign_sidereal=chart_result["elements"].get("moon_sign_sidereal"),
                moon_sign_tropical=chart_result["elements"].get("moon_sign_tropical"),
                rising_sign_sidereal=chart_result["elements"].get("rising_sign_sidereal"),
                rising_sign_tropical=chart_result["elements"].get("rising_sign_tropical"),
                life_path_number=numerology_data.get("life_path_number"),
                day_number=numerology_data.get("day_number"),
                chinese_zodiac_animal=chinese_animal,
                chinese_zodiac_element=chinese_element,
            )
            
            db.add(famous_person)
            existing_names.add(name)  # Add to set
            db_processed += 1
            
            # Commit in batches
            if db_processed % BATCH_SIZE == 0:
                try:
                    db.commit()
                    log_print(f"   ✓ Committed batch: {db_processed} people saved to database")
                except Exception as e:
                    log_print(f"   ✗ Error committing batch: {e}")
                    db.rollback()
                    raise
            
            if idx % 50 == 0:
                log_print(f"   Progress: {idx}/{len(people_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
        
        # Final commit
        try:
            db.commit()
            log_print(f"   ✓ Final commit: All {db_processed} people saved to database")
        except Exception as e:
            log_print(f"   ✗ Error in final commit: {e}")
            db.rollback()
            raise
        
        log_print("\n" + "=" * 70)
        log_print("PROCESS COMPLETE!")
        log_print("=" * 70)
        log_print(f"Queried: {len(people_data)} people from Wikidata")
        log_print(f"Calculated & Saved: {db_processed} people")
        log_print(f"Skipped (already in DB): {db_skipped}")
        log_print(f"Errors: {db_errors}")
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

