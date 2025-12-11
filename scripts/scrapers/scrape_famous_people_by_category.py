"""
Scrape famous people by occupation category with notability filters.

This approach gets recognizable, famous people by querying specific occupations

and applying notability filters.



Strategy:

- Layer A: Filter by occupation (actors, musicians, athletes, etc.)

- Layer B: Add notability filters (sitelinks, enwiki presence)

- Step 3: Target counts per category for balanced results

- Step 4: Post-process with fame ranking

"""

import os

import sys

import time

import json

import logging

import requests

from datetime import datetime

from typing import Dict, Optional, List

from collections import defaultdict



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

REQUEST_DELAY = 0.5  # Delay between requests

BATCH_SIZE = 50      # Commit to database every N records



OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")

if not OPENCAGE_KEY:

    logger.warning("OPENCAGE_KEY not set. Geocoding will fail.")


# Global flag to disable geocoding if API quota exceeded
GEOCODING_DISABLED = False

# Cache for geocoding results to avoid duplicate requests
GEOCODING_CACHE = {}

# Fame / notability thresholds (tunable)

MIN_SITELINKS = 10           # Minimum number of Wikidata sitelinks to keep a person

REQUIRE_ENWIKI = True        # Require an English Wikipedia page to consider "famous"



# ============================================================================

# OCCUPATION CATEGORIES WITH TARGET COUNTS

# (QIDs updated + cleaned to match actual occupations)

# ============================================================================



OCCUPATION_TARGETS = {

    "actors": {

        # Actor, television actor, film actor

        "qids": ["Q33999", "Q10798782", "Q10800557"],

        "target": 1000,

        "description": "Actors"

    },

    "musicians": {

        # Musician, singer, singer-songwriter

        "qids": ["Q639669", "Q177220", "Q488205"],

        "target": 1000,

        "description": "Musicians"

    },

    "athletes": {

        # Athlete, association football player, basketball player, American football player

        "qids": ["Q2066131", "Q937857", "Q3665646", "Q19204627"],

        "target": 800,

        "description": "Athletes"

    },

    "politicians": {

        # Politician

        "qids": ["Q82955"],

        "target": 400,

        "description": "Politicians"

    },

    "influencers": {

        # Internet celebrity, YouTuber

        "qids": ["Q3282637", "Q17125263"],

        "target": 500,

        "description": "Influencers / creators"

    },

    "models": {

        # Model, fashion model

        "qids": ["Q4610556", "Q3357567"],

        "target": 200,

        "description": "Models"

    },

    "authors": {

        # Writer

        "qids": ["Q36180"],

        "target": 300,

        "description": "Authors / writers"

    },

    "entrepreneurs": {

        # Businessperson

        "qids": ["Q43845"],

        "target": 300,

        "description": "Entrepreneurs"

    },

}



# ============================================================================

# SPARQL QUERIES

# ============================================================================



def get_people_by_occupation(occupation_qids: List[str], limit: int = 1000) -> List[Dict]:

    """

    Get people by occupation - queries each occupation separately and combines.

    

    Args:

        occupation_qids: List of occupation QIDs to query

        limit: Maximum number of people to return

    """

    all_results = []

    seen_qids = set()

    chunk_size = 100

    # Distribute requested limit across occupations and add some buffer

    limit_per_occupation = max(100, limit // max(len(occupation_qids), 1) + 100)

    

    # Query each occupation separately (simpler and more reliable)

    for occupation_qid in occupation_qids:

        if len(all_results) >= limit:

            break

        

        logger.info(f"  Querying occupation {occupation_qid}...")

        occupation_results = []

        offset = 0

        

        # A few pages of results per occupation

        for _ in range((limit_per_occupation // chunk_size) + 3):

            if len(occupation_results) >= limit_per_occupation:

                break

            

            # Simple query for single occupation

            query = f"""

            SELECT ?person ?birthDate ?birthPlace

            WHERE {{

                ?person wdt:P31 wd:Q5 .              # Instance of: Human

                ?person wdt:P569 ?birthDate .        # Has date of birth

                FILTER(YEAR(?birthDate) >= 1800) .   # Only people born after 1800

                ?person wdt:P19 ?birthPlace .        # Has place of birth

                ?person wdt:P106 wd:{occupation_qid} .  # Has this occupation

            }}

            LIMIT {chunk_size}

            OFFSET {offset}

            """

            

            chunk_results = execute_sparql_query(query)

            

            if not chunk_results:

                break

            

            # Filter duplicates across all occupations

            for person in chunk_results:

                qid = person.get("qid")

                if qid and qid not in seen_qids:

                    seen_qids.add(qid)

                    occupation_results.append(person)

                    if len(occupation_results) >= limit_per_occupation:

                        break

            

            if len(chunk_results) < chunk_size:

                break

            

            offset += chunk_size

            time.sleep(REQUEST_DELAY)

        

        all_results.extend(occupation_results)

        logger.info(f"  Occupation {occupation_qid}: {len(occupation_results)} people (total: {len(all_results)})")

    

    return all_results[:limit]



def execute_sparql_query(query: str, max_retries: int = 3) -> List[Dict]:

    """Execute a SPARQL query against Wikidata with retry logic."""

    url = "https://query.wikidata.org/sparql"

    headers = {

        "User-Agent": USER_AGENT,

        "Accept": "application/sparql-results+json"

    }

    

    for attempt in range(max_retries):

        try:

            time.sleep(REQUEST_DELAY)

            timeout = 60 if attempt == 0 else 90

            response = requests.get(

                url,

                params={"query": query, "format": "json"},

                headers=headers,

                timeout=timeout

            )

            response.raise_for_status()

            

            data = response.json()

            results = []

            

            for binding in data.get("results", {}).get("bindings", []):

                person_data = {}

                

                # Extract person QID

                if "person" in binding:

                    person_data["qid"] = binding["person"]["value"].split("/")[-1]

                

                # Extract birth date

                if "birthDate" in binding:

                    birth_date_str = binding["birthDate"]["value"]

                    try:

                        from datetime import datetime as dt

                        date_str_clean = birth_date_str.replace("Z", "+00:00")

                        date_obj = dt.fromisoformat(date_str_clean)

                        person_data["birth_date"] = {

                            "year": date_obj.year,

                            "month": date_obj.month,

                            "day": date_obj.day

                        }

                    except Exception:

                        date_part = birth_date_str.split("T")[0]

                        parts = date_part.split("-")

                        if len(parts) >= 1 and parts[0].strip():

                            try:

                                year = int(parts[0])

                                month = int(parts[1]) if len(parts) >= 2 and parts[1].strip() else None

                                day = int(parts[2]) if len(parts) >= 3 and parts[2].strip() else None

                                if year and month:

                                    person_data["birth_date"] = {

                                        "year": year,

                                        "month": month,

                                        "day": day if day else 1

                                    }

                            except (ValueError, IndexError):

                                pass

                

                # Extract birth place QID

                if "birthPlace" in binding:

                    place_uri = binding["birthPlace"]["value"]

                    place_qid = place_uri.split("/")[-1]

                    person_data["birth_place_qid"] = place_qid

                

                if person_data.get("qid") and person_data.get("birth_date"):

                    results.append(person_data)

            

            return results

                

        except requests.exceptions.Timeout as e:

            if attempt < max_retries - 1:

                wait_time = (2 ** attempt) * 10

                logger.warning(

                    f"SPARQL query timeout (attempt {attempt + 1}/{max_retries}). "

                    f"Retrying in {wait_time}s..."

                )

                time.sleep(wait_time)

                continue

            else:

                logger.error(f"SPARQL query timeout after {max_retries} attempts: {e}")

                return []

        except Exception as e:

            if attempt < max_retries - 1:

                wait_time = (2 ** attempt) * 5

                logger.warning(

                    f"SPARQL query error (attempt {attempt + 1}/{max_retries}): {e}. "

                    f"Retrying in {wait_time}s..."

                )

                time.sleep(wait_time)

                continue

            else:

                logger.error(f"SPARQL query error after {max_retries} attempts: {e}")

                return []

    

    return []



def fetch_labels_from_wikidata_api(qids: List[str]) -> Dict[str, Dict[str, str]]:

    """

    Fetch labels, descriptions, and sitelink info for QIDs using Wikidata API.

    Also used as a lightweight "fame" signal:

    - sitelinks_count: how many wikis link to this entity

    - has_enwiki: whether there is an English Wikipedia article

    """

    if not qids:

        return {}

    

    labels: Dict[str, Dict[str, str]] = {}

    batch_size = 50

    

    for i in range(0, len(qids), batch_size):

        batch = qids[i:i + batch_size]

        qid_string = "|".join(batch)

        

        url = "https://www.wikidata.org/w/api.php"

        params = {

            "action": "wbgetentities",

            "ids": qid_string,

            "props": "labels|descriptions|sitelinks",

            "languages": "en",

            "format": "json"

        }

        

        try:

            time.sleep(0.5)

            response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)

            response.raise_for_status()

            

            data = response.json()

            entities = data.get("entities", {})

            

            for qid, entity in entities.items():

                if not isinstance(entity, dict):

                    continue

                

                labels_data = entity.get("labels", {})

                desc_data = entity.get("descriptions", {})

                sitelinks_data = entity.get("sitelinks", {}) or {}

                

                label = labels_data.get("en", {}).get("value", "") if labels_data.get("en") else ""

                description = desc_data.get("en", {}).get("value", "") if desc_data.get("en") else ""

                sitelinks_count = len(sitelinks_data)

                has_enwiki = "enwiki" in sitelinks_data

                

                labels[qid] = {

                    "label": label,

                    "description": description,

                    "sitelinks_count": sitelinks_count,

                    "has_enwiki": has_enwiki,

                }

        except Exception as e:

            logger.warning(f"Error fetching labels for batch: {e}")

            continue

    

    return labels



# ============================================================================

# CHART CALCULATION (same as before)

# ============================================================================



def get_coordinates_from_wikidata(place_qid: str) -> Optional[Dict]:
    """
    Get coordinates directly from Wikidata using the place QID.
    This is free and has no API limits.
    """
    if not place_qid:
        return None
    
    # Check cache first
    cache_key = f"wikidata:{place_qid}"
    if cache_key in GEOCODING_CACHE:
        return GEOCODING_CACHE[cache_key]
    
    try:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": place_qid,
            "props": "claims",
            "format": "json"
        }
        
        time.sleep(0.2)  # Be respectful to Wikidata
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        entities = data.get("entities", {})
        entity = entities.get(place_qid, {})
        claims = entity.get("claims", {})
        
        # P625 is the coordinate location property
        if "P625" in claims:
            coordinate_claim = claims["P625"][0]
            mainsnak = coordinate_claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            
            latitude = value.get("latitude")
            longitude = value.get("longitude")
            
            if latitude and longitude:
                # Try to get timezone from the place (P421 is timezone property)
                timezone = "UTC"
                if "P421" in claims:
                    tz_claim = claims["P421"][0]
                    tz_mainsnak = tz_claim.get("mainsnak", {})
                    tz_datavalue = tz_mainsnak.get("datavalue", {})
                    tz_value = tz_datavalue.get("value", "")
                    if tz_value:
                        timezone = tz_value
                
                result = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone
                }
                GEOCODING_CACHE[cache_key] = result
                return result
    except Exception as e:
        logger.debug(f"Failed to get coordinates from Wikidata for {place_qid}: {e}")
    
    return None


def geocode_with_nominatim(location: str) -> Optional[Dict]:
    """
    Geocode using Nominatim (OpenStreetMap) - free and generous limits.
    Requires User-Agent and rate limiting (max 1 request/second).
    """
    # Check cache first
    cache_key = f"nominatim:{location}"
    if cache_key in GEOCODING_CACHE:
        return GEOCODING_CACHE[cache_key]
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": USER_AGENT
        }
        
        time.sleep(1.1)  # Nominatim requires max 1 request/second
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            result_data = data[0]
            lat = float(result_data.get("lat", 0))
            lon = float(result_data.get("lon", 0))
            
            if lat and lon:
                # Nominatim doesn't provide timezone, so we'll use UTC
                # (timezone can be calculated later if needed)
                result = {
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": "UTC"  # Will need to calculate timezone separately
                }
                GEOCODING_CACHE[cache_key] = result
                return result
    except Exception as e:
        logger.debug(f"Geocoding with Nominatim failed for {location}: {e}")
    
    return None


def geocode_location(location: str, place_qid: Optional[str] = None) -> Optional[Dict]:
    """
    Geocode location using free sources:
    1. Try Wikidata coordinates (if place_qid provided) - no limits
    2. Try Nominatim (OpenStreetMap) - free, generous limits
    """

    # Check cache first (by location name)
    if location in GEOCODING_CACHE:
        return GEOCODING_CACHE[location]
    
    # Method 1: Try Wikidata coordinates first (free, no limits)
    if place_qid:
        wikidata_result = get_coordinates_from_wikidata(place_qid)
        if wikidata_result:
            GEOCODING_CACHE[location] = wikidata_result
            return wikidata_result
    
    # Method 2: Try Nominatim (OpenStreetMap) - free
    nominatim_result = geocode_with_nominatim(location)
    if nominatim_result:
        GEOCODING_CACHE[location] = nominatim_result
        return nominatim_result
    
    # If both methods fail, return None
    logger.warning(f"Geocoding failed for {location} (tried Wikidata and Nominatim)")
    return None

    

    try:

        url = "https://api.opencagedata.com/geocode/v1/json"

        params = {

            "q": location,

            "key": OPENCAGE_KEY,

            "limit": 1

        }

        headers = {"User-Agent": USER_AGENT}

        

        time.sleep(0.1)

        response = requests.get(url, params=params, headers=headers, timeout=10)

        
        # Check for 402 Payment Required before raising
        if response.status_code == 402:
            GEOCODING_DISABLED = True
            logger.error(
                "OpenCage API returned 402 Payment Required. "
                "Geocoding disabled for remaining requests. "
                "Please check your API key quota or upgrade your plan."
            )
            return None
        
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

    except requests.exceptions.HTTPError as e:
        # Check for 402 in the exception as well
        if hasattr(e.response, 'status_code') and e.response.status_code == 402:
            GEOCODING_DISABLED = True
            logger.error(
                "OpenCage API returned 402 Payment Required. "
                "Geocoding disabled for remaining requests. "
                "Please check your API key quota or upgrade your plan."
            )
            return None
        # For other HTTP errors, log but don't disable
        logger.warning(f"Geocoding failed for {location}: {e}")
    except Exception as e:

        logger.warning(f"Geocoding failed for {location}: {e}")

    

    return None



def calculate_person_chart(person_data: Dict) -> Optional[Dict]:

    """Calculate birth chart for a person."""

    birth_date = person_data.get("birth_date")

    birth_location = person_data.get("birth_location")

    birth_place_qid = person_data.get("birth_place_qid")

    

    if not birth_date or not birth_location:

        return None

    

    geo = geocode_location(birth_location, place_qid=birth_place_qid)

    if not geo:

        return None

    

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

        

        numerology_data = calculate_numerology(

            birth_date["day"],

            birth_date["month"],

            birth_date["year"]

        )

        

        chinese_zodiac = get_chinese_zodiac_and_element(

            birth_date["year"],

            birth_date["month"],

            birth_date["day"]

        )

        

        chart_data = chart.get_full_chart_data(

            numerology_data,

            None,

            chinese_zodiac,

            unknown_time

        )

        

        elements = {}

        for body in chart.celestial_bodies:

            if body.name == "Sun":

                elements["sun_sign_sidereal"] = body.sign

            elif body.name == "Moon":

                elements["moon_sign_sidereal"] = body.sign

            elif body.name == "Ascendant" and not unknown_time:

                elements["rising_sign_sidereal"] = body.sign

        

        for body in chart.tropical_bodies:

            if body.name == "Sun":

                elements["sun_sign_tropical"] = body.sign

            elif body.name == "Moon":

                elements["moon_sign_tropical"] = body.sign

            elif body.name == "Ascendant" and not unknown_time:

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

    """Main function to scrape famous people by category."""

    output_file = open("famous_people_by_category_output.txt", "w", encoding="utf-8")

    

    def log_print(msg):

        print(msg)

        output_file.write(str(msg) + "\n")

        output_file.flush()

    

    log_print("=" * 70)

    log_print("FAMOUS PEOPLE SCRAPER - BY CATEGORY")

    log_print("=" * 70)

    log_print(f"Started: {datetime.now()}")

    log_print(f"OPENCAGE_KEY: {'SET' if OPENCAGE_KEY else 'NOT SET'}")

    log_print("=" * 70)

    

    init_db()

    db = SessionLocal()

    

    try:

        # Check current database count

        current_count = db.query(FamousPerson).count()

        log_print(f"\nCurrent database count: {current_count} people")

        

        # Pre-load existing names

        existing_names = {row[0] for row in db.query(FamousPerson.name).all()}

        log_print(f"Found {len(existing_names)} people already in database (will skip)")

        

        all_people_by_category: Dict[str, List[Dict]] = {}

        total_fetched = 0

        

        # Step 1: Query each category

        log_print("\n" + "=" * 70)

        log_print("STEP 1: QUERYING BY OCCUPATION CATEGORY")

        log_print("=" * 70)

        

        for category, config in OCCUPATION_TARGETS.items():

            log_print(f"\nCategory: {config['description']}")

            log_print(f"Target: {config['target']} people")

            log_print(f"Occupations: {', '.join(config['qids'])}")

            

            people = get_people_by_occupation(

                occupation_qids=config["qids"],

                limit=config["target"] * 2  # Get extra to account for filtering

            )

            

            all_people_by_category[category] = people

            total_fetched += len(people)

            log_print(f"  ✓ Fetched {len(people)} people")

        

        log_print(f"\nTotal fetched from Wikidata: {total_fetched} people")

        

        # Step 2: Fetch labels + sitelinks (fame signal)

        log_print("\n" + "=" * 70)

        log_print("STEP 2: FETCHING LABELS")

        log_print("=" * 70)

        

        all_qids: List[str] = []

        all_place_qids: List[str] = []

        for category_people in all_people_by_category.values():

            for person in category_people:

                if person.get("qid"):

                    all_qids.append(person["qid"])

                if person.get("birth_place_qid"):

                    all_place_qids.append(person["birth_place_qid"])

        

        unique_qids = list(set(all_qids + all_place_qids))

        log_print(f"Fetching labels for {len(unique_qids)} QIDs...")

        

        labels = fetch_labels_from_wikidata_api(unique_qids)

        log_print(f"✓ Fetched {len(labels)} labels")

        

        # Update results with labels and fame signals

        for category_people in all_people_by_category.values():

            for person in category_people:

                qid = person.get("qid")

                if qid and qid in labels:

                    person["name"] = labels[qid].get("label", "")

                    person["description"] = labels[qid].get("description", "")

                    person["sitelinks_count"] = labels[qid].get("sitelinks_count", 0)

                    person["has_enwiki"] = labels[qid].get("has_enwiki", False)

                    

                    if person["name"]:

                        name_encoded = person["name"].replace(" ", "_")

                        person["wikipedia_url"] = f"https://en.wikipedia.org/wiki/{name_encoded}"

                else:

                    person["sitelinks_count"] = 0

                    person["has_enwiki"] = False

                

                place_qid = person.get("birth_place_qid")

                if place_qid and place_qid in labels:

                    person["birth_location"] = labels[place_qid].get("label", "")

        

        # Step 3: Process and save to database

        log_print("\n" + "=" * 70)

        log_print("STEP 3: PROCESSING AND SAVING TO DATABASE")

        log_print("=" * 70)

        

        db_processed = 0

        db_skipped = 0

        db_errors = 0

        

        # Combine all categories, apply notability filter, then sort

        all_people: List[Dict] = []

        for category, people in all_people_by_category.items():

            for person in people:

                if not (person.get("name") and person.get("birth_date")):

                    continue

                if not person.get("birth_location"):

                    continue

                

                # Ensure birth_location is not just a raw QID/URL

                location = person.get("birth_location", "")

                is_qid_like = (

                    location.startswith("Q")

                    and len(location) > 1

                    and location[1:].isdigit()

                )

                if is_qid_like or "wikidata.org" in location or location.startswith("http"):

                    continue

                

                # Fame filter: require English Wikipedia and/or enough sitelinks

                sitelinks_count = int(person.get("sitelinks_count", 0) or 0)

                has_enwiki = bool(person.get("has_enwiki", False))

                

                if REQUIRE_ENWIKI and not has_enwiki:

                    continue

                if sitelinks_count < MIN_SITELINKS:

                    continue

                

                person["category"] = category

                all_people.append(person)

        

        # Sort by category priority and then by sitelinks_count (descending)

        category_priority = {

            "actors": 1,

            "musicians": 2,

            "athletes": 3,

            "influencers": 4,

            "politicians": 5,

            "models": 6,

            "authors": 7,

            "entrepreneurs": 8,

        }

        all_people.sort(

            key=lambda x: (

                category_priority.get(x.get("category", ""), 99),

                -int(x.get("sitelinks_count", 0) or 0),

            )

        )

        

        log_print(

            f"Processing {len(all_people)} people with complete data "

            f"after notability filters (enwiki + sitelinks >= {MIN_SITELINKS})..."

        )

        

        for idx, person_data in enumerate(all_people, 1):

            name = person_data.get("name", "")

            if not name:

                db_errors += 1

                if idx % 50 == 0:

                    log_print(

                        f"   Progress: {idx}/{len(all_people)} "

                        f"(processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})"

                    )

                continue

            

            # Check if already exists (by name)

            if name in existing_names:

                db_skipped += 1

                if idx % 50 == 0:

                    log_print(

                        f"   Progress: {idx}/{len(all_people)} "

                        f"(processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})"

                    )

                continue

            

            existing = db.query(FamousPerson).filter(FamousPerson.name == name).first()

            if existing:

                existing_names.add(name)

                db_skipped += 1

                if idx % 50 == 0:

                    log_print(

                        f"   Progress: {idx}/{len(all_people)} "

                        f"(processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})"

                    )

                continue

            

            # Calculate chart

            chart_result = calculate_person_chart(person_data)

            if not chart_result:

                db_errors += 1

                if idx % 50 == 0:

                    log_print(

                        f"   Progress: {idx}/{len(all_people)} "

                        f"(processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})"

                    )

                continue

            

            # Extract data

            birth_date = person_data.get("birth_date", {})

            numerology_data = chart_result["chart_data"].get("numerology", {})

            chinese_zodiac_str = chart_result["chart_data"].get("chinese_zodiac", "")

            

            chinese_animal = None

            chinese_element = None

            if chinese_zodiac_str and isinstance(chinese_zodiac_str, str) and chinese_zodiac_str != "N/A":

                parts = chinese_zodiac_str.strip().split()

                if len(parts) >= 2:

                    chinese_element = parts[0]

                    chinese_animal = parts[1]

            

            # Create database entry

            famous_person = FamousPerson(

                name=name,

                wikipedia_url=person_data.get("wikipedia_url", ""),

                occupation=person_data.get("category", ""),

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

            existing_names.add(name)

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

                log_print(

                    f"   Progress: {idx}/{len(all_people)} "

                    f"(processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})"

                )

        

        # Final commit

        try:

            db.commit()

            log_print(f"\n   ✓ Final commit: All {db_processed} people saved to database")

        except Exception as e:

            log_print(f"\n   ✗ Error in final commit: {e}")

            db.rollback()

            raise

        

        log_print("\n" + "=" * 70)

        log_print("PROCESS COMPLETE!")

        log_print("=" * 70)

        log_print(f"Fetched (raw): {total_fetched} people from Wikidata")

        log_print(f"After notability filter: {len(all_people)} candidates")

        log_print(f"Calculated & Saved: {db_processed} people")

        log_print(f"Skipped (already in DB): {db_skipped}")

        log_print(f"Errors: {db_errors}")

        log_print(f"Final database count: {db.query(FamousPerson).count()} people")

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
