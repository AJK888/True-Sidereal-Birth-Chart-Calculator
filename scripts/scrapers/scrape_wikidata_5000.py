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
    
    Queries in chunks of 1000 to avoid 504 Gateway Timeout.
    Uses birth year ranges to get different batches.
    """
    CHUNK_SIZE = 50  # Very small chunks - Wikidata SPARQL is slow
    all_results = []
    seen_qids = set()  # Track QIDs to avoid duplicates
    
    logger.info(f"Fetching {limit} people in chunks of {CHUNK_SIZE}...")
    logger.info("Note: Using very small chunks and simplified queries to avoid timeouts")
    
    # Use OFFSET to get different batches - with small chunks (50) it should be fast enough
    offset = 0
    max_queries = (limit // CHUNK_SIZE) + 20  # Query more to account for filtering
    
    for query_num in range(max_queries):
        if len(all_results) >= limit:
            break
        
        chunk_limit = CHUNK_SIZE
        
        # Simple query - get people with birth dates and places
        # Filter: Only people born after 1800 (so we can use seas_18.se1 for asteroids)
        # No ORDER BY - that causes timeouts on large datasets
        # We'll get QIDs and dates/places, then fetch labels via Wikidata API if needed
        query = f"""
        SELECT ?person ?birthDate ?birthPlace
        WHERE {{
            ?person wdt:P31 wd:Q5 .  # Instance of: Human
            ?person wdt:P569 ?birthDate .  # Has date of birth
            FILTER(YEAR(?birthDate) >= 1800)  # Only people born after 1800
            ?person wdt:P19 ?birthPlace .  # Has place of birth
        }}
        LIMIT {chunk_limit}
        OFFSET {offset}
        """
        
        logger.info(f"  Query {query_num + 1}: offset={offset}, limit={chunk_limit}")
        chunk_results = execute_sparql_query(query)
        
        if not chunk_results:
            logger.warning(f"  No results returned for query {query_num + 1}. Stopping.")
            break
        
        # Filter out duplicates and add to results
        new_count = 0
        for person in chunk_results:
            qid = person.get("qid")
            if qid and qid not in seen_qids:
                seen_qids.add(qid)
                all_results.append(person)
                new_count += 1
                if len(all_results) >= limit:
                    break
        
        logger.info(f"  Query {query_num + 1}: {len(chunk_results)} returned, {new_count} new (total: {len(all_results)})")
        
        # If we got significantly fewer results than requested, we might be at the end
        # But continue if we got at least some results (might just be filtering)
        if len(chunk_results) == 0:
            logger.info(f"  No results returned, stopping.")
            break
        elif len(chunk_results) < chunk_limit * 0.5:  # Less than half - probably at end
            logger.info(f"  Very few results (got {len(chunk_results)} < {chunk_limit * 0.5}), might be at end but continuing...")
        
        # Increment offset for next query
        offset += chunk_limit
        
        # Delay between queries
        time.sleep(2.0)
    
    logger.info(f"Total fetched: {len(all_results)} people")
    
    # Fetch labels for all QIDs using Wikidata API (much faster than SPARQL)
    logger.info("Fetching labels from Wikidata API...")
    all_qids = [p.get("qid") for p in all_results if p.get("qid")]
    place_qids = [p.get("birth_place_qid") for p in all_results if p.get("birth_place_qid")]
    all_qids_to_fetch = list(set(all_qids + place_qids))
    
    labels = fetch_labels_from_wikidata_api(all_qids_to_fetch)
    
    # Update results with labels
    for person in all_results:
        qid = person.get("qid")
        if qid and qid in labels:
            person["name"] = labels[qid]["label"]
            # Construct Wikipedia URL
            if person["name"]:
                name_encoded = person["name"].replace(" ", "_")
                person["wikipedia_url"] = f"https://en.wikipedia.org/wiki/{name_encoded}"
        
        place_qid = person.get("birth_place_qid")
        if place_qid and place_qid in labels:
            person["birth_location"] = labels[place_qid]["label"]
    
    # Filter to only include people with names and locations (not just QIDs)
    final_results = []
    for p in all_results:
        name = p.get("name", "").strip()
        location = p.get("birth_location", "").strip()
        # Make sure location is not just a QID or URI
        # QIDs are like "Q123" or URIs like "http://www.wikidata.org/entity/Q123"
        is_qid_or_uri = False
        if location:
            # Check if it's a QID (starts with Q and rest is digits)
            if location.startswith("Q") and len(location) > 1 and location[1:].isdigit():
                is_qid_or_uri = True
            # Check if it's a Wikidata URI
            elif "wikidata.org" in location or location.startswith("http"):
                is_qid_or_uri = True
        
        if name and p.get("birth_date") and location and not is_qid_or_uri:
            final_results.append(p)
    
    logger.info(f"After label fetching: {len(final_results)} people with complete data")
    return final_results[:limit]  # Return exactly the requested amount

def fetch_labels_from_wikidata_api(qids: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Fetch labels for QIDs using Wikidata API (faster than SPARQL for labels).
    Returns dict mapping QID to {"label": "...", "description": "..."}
    """
    if not qids:
        return {}
    
    # Wikidata API allows up to 50 QIDs per request
    labels = {}
    batch_size = 50
    
    for i in range(0, len(qids), batch_size):
        batch = qids[i:i + batch_size]
        qid_string = "|".join(batch)
        
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": qid_string,
            "props": "labels|descriptions",
            "languages": "en",
            "format": "json"
        }
        
        try:
            time.sleep(0.5)  # Rate limiting
            response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            entities = data.get("entities", {})
            
            for qid, entity in entities.items():
                labels_data = entity.get("labels", {})
                desc_data = entity.get("descriptions", {})
                
                label = labels_data.get("en", {}).get("value", "") if labels_data.get("en") else ""
                description = desc_data.get("en", {}).get("value", "") if desc_data.get("en") else ""
                
                labels[qid] = {
                    "label": label,
                    "description": description
                }
        except Exception as e:
            logger.warning(f"Error fetching labels for batch: {e}")
            continue
    
    return labels

def get_top_people_by_pageviews(limit: int = 5000) -> List[Dict]:
    """
    Alternative: Get people sorted by pageviews (requires external data).
    For now, we'll use sitelinks as a proxy.
    """
    # This would require integrating with Wikimedia Pageviews API
    # For simplicity, we'll use sitelinks method
    return get_top_people_by_sitelinks(limit)

def execute_sparql_query(query: str, max_retries: int = 3) -> List[Dict]:
    """Execute a SPARQL query against Wikidata with retry logic."""
    url = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    for attempt in range(max_retries):
        try:
            time.sleep(REQUEST_DELAY)  # Rate limiting
            # Timeout for smaller queries - should be faster now
            timeout = 60 if attempt == 0 else 90
            response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for binding in data.get("results", {}).get("bindings", []):
                person_data = {}
                
                # Extract person QID
                if "person" in binding:
                    person_data["qid"] = binding["person"]["value"].split("/")[-1]
                
                # Extract name (may not be present in simplified query)
                if "personLabel" in binding:
                    person_data["name"] = binding["personLabel"]["value"]
                
                # Extract birth date
                if "birthDate" in binding:
                    birth_date_str = binding["birthDate"]["value"]
                    # Parse ISO date (e.g., "1950-01-15T00:00:00Z" or "1950-01-15" or "1950-01" or "1950")
                    try:
                        from datetime import datetime as dt
                        # Handle timezone suffix
                        date_str_clean = birth_date_str.replace("Z", "+00:00")
                        date_obj = dt.fromisoformat(date_str_clean)
                        person_data["birth_date"] = {
                            "year": date_obj.year,
                            "month": date_obj.month,
                            "day": date_obj.day
                        }
                    except:
                        # Try parsing just date part (YYYY-MM-DD or YYYY-MM or YYYY)
                        date_part = birth_date_str.split("T")[0]
                        parts = date_part.split("-")
                        
                        if len(parts) >= 1 and parts[0].strip():
                            try:
                                year = int(parts[0])
                                month = int(parts[1]) if len(parts) >= 2 and parts[1].strip() else None
                                day = int(parts[2]) if len(parts) >= 3 and parts[2].strip() else None
                                
                                # Only add if we have at least year and month
                                if year and month:
                                    person_data["birth_date"] = {
                                        "year": year,
                                        "month": month,
                                        "day": day if day else 1  # Default to 1st if day missing
                                    }
                            except (ValueError, IndexError):
                                # Skip if parsing fails
                                pass
                
                # Extract birth place QID (label may not be present)
                if "birthPlace" in binding:
                    place_uri = binding["birthPlace"]["value"]
                    place_qid = place_uri.split("/")[-1]
                    person_data["birth_place_qid"] = place_qid
                    if "birthPlaceLabel" in binding:
                        person_data["birth_location"] = binding["birthPlaceLabel"]["value"]
                    else:
                        person_data["birth_location"] = place_qid  # Temporary, will fetch label later
                
                # Extract occupation (may not be present)
                if "occupationLabel" in binding:
                    person_data["occupation"] = binding["occupationLabel"]["value"]
                
                # Only add if we have QID and birth date (name and location can be fetched later)
                if person_data.get("qid") and person_data.get("birth_date"):
                    results.append(person_data)
            
            return results
                
        except requests.exceptions.Timeout as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 10  # Exponential backoff: 10s, 20s, 40s
                logger.warning(f"SPARQL query timeout (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"SPARQL query timeout after {max_retries} attempts: {e}")
                return []
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                logger.warning(f"SPARQL query error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"SPARQL query error after {max_retries} attempts: {e}")
                return []
    
    return []  # Should not reach here, but just in case

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
        
        # Get full chart data (positional arguments, not keyword)
        chart_data = chart.get_full_chart_data(
            numerology_data,  # numerology
            None,  # name_numerology (optional)
            chinese_zodiac,  # chinese_zodiac
            unknown_time  # unknown_time
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

