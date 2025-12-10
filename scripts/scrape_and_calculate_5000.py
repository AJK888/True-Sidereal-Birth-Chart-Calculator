"""
Complete script to scrape 5000 top Wikipedia people and calculate their charts.

This script:
1. Gets a list of 5000 famous people from Wikipedia (using multiple sources)
2. Scrapes their birth dates and locations
3. Calculates their birth charts with numerology and Chinese zodiac
4. Stores everything in the database

Usage:
    python scripts/scrape_and_calculate_5000.py

Requirements:
    pip install wikipedia-api requests sqlalchemy aiosqlite pyswisseph

Environment Variables:
    OPENCAGE_KEY - Required for geocoding birth locations
"""

import os
import sys
import time
import json
import re
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional, List
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import wikipediaapi
    from database import SessionLocal, FamousPerson, init_db
    from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element
except ImportError as e:
    print(f"Required packages not installed: {e}")
    print("Run: pip install wikipedia-api requests sqlalchemy aiosqlite pyswisseph")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

USER_AGENT = "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"
REQUEST_DELAY = 0.6  # 100 requests/minute (safe limit)
MAX_PEOPLE = 5000
BATCH_SIZE = 50  # Commit to database every N records

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
if not OPENCAGE_KEY:
    logger.warning("OPENCAGE_KEY not set. Geocoding will fail for locations that need it.")
    logger.warning("Set it with: $env:OPENCAGE_KEY='your_key'")

WIKI = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT
)

# ============================================================================
# RATE LIMITING
# ============================================================================

class RateLimiter:
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.request_times = []
        self.min_delay = 60.0 / requests_per_minute
    
    def wait_if_needed(self):
        now = time.time()
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        if len(self.request_times) >= self.requests_per_minute:
            oldest_request = min(self.request_times)
            wait_time = 60 - (now - oldest_request) + 1
            if wait_time > 0:
                logger.warning(f"Rate limit approaching. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
        
        if self.request_times:
            time_since_last = now - self.request_times[-1]
            if time_since_last < self.min_delay:
                time.sleep(self.min_delay - time_since_last)
        
        self.request_times.append(time.time())

rate_limiter = RateLimiter()

# ============================================================================
# WIKIPEDIA DATA EXTRACTION
# ============================================================================

def parse_birth_date(text: str) -> Optional[Dict]:
    """Parse birth date from Wikipedia infobox text."""
    if not text:
        return None
    
    # Pattern 1: {{birth date|year|month|day}}
    pattern1 = r'\{\{birth date\|(\d{4})\|(\d{1,2})\|(\d{1,2})\}\}'
    match = re.search(pattern1, text)
    if match:
        return {'year': int(match.group(1)), 'month': int(match.group(2)), 'day': int(match.group(3))}
    
    # Pattern 2: {{birth date|year|month|day|df=yes}}
    pattern2 = r'\{\{birth date\|(\d{4})\|(\d{1,2})\|(\d{1,2})\|df=yes\}\}'
    match = re.search(pattern2, text)
    if match:
        return {'year': int(match.group(1)), 'month': int(match.group(2)), 'day': int(match.group(3))}
    
    # Pattern 3: Nested templates like {{circa|{{birth date|...}}}}
    pattern3 = r'\{\{[^}]*birth date\|(\d{4})\|(\d{1,2})\|(\d{1,2})[^}]*\}\}'
    match = re.search(pattern3, text)
    if match:
        return {'year': int(match.group(1)), 'month': int(match.group(2)), 'day': int(match.group(3))}
    
    return None

def parse_birth_location(text: str) -> str:
    """Parse and clean birth location from Wikipedia infobox."""
    if not text:
        return ""
    
    # Find birth_place parameter
    pattern = r'\{\{Infobox[^}]*\|[^}]*birth_place\s*=\s*([^|}]+)'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        location = match.group(1).strip()
    else:
        # Try alternative patterns
        pattern2 = r'birth_place\s*=\s*([^|}]+)'
        match = re.search(pattern2, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
        else:
            return ""
    
    # Clean up wiki markup
    location = re.sub(r'\[\[([^\]]+)\]\]', r'\1', location)  # Remove [[links]] but keep text
    location = re.sub(r'\{\{[^}]+\}\}', '', location)  # Remove {{templates}}
    location = re.sub(r'<[^>]+>', '', location)  # Remove HTML tags
    location = location.split('|')[0]  # Take first part if pipe-separated
    location = re.sub(r'[,\s]*\{\{[^}]*', '', location)  # Remove templates that start mid-string
    location = re.sub(r'\s+', ' ', location).strip()  # Normalize whitespace
    
    # Remove any parts containing {{
    parts = location.split(',')
    cleaned_parts = [p.strip() for p in parts if '{' not in p]
    location = ', '.join(cleaned_parts)
    
    return location

def get_infobox_data(page_title: str, retry_count: int = 0) -> Dict:
    """Get birth date and location from Wikipedia page infobox."""
    rate_limiter.wait_if_needed()
    
    try:
        page = WIKI.page(page_title)
        if not page.exists():
            return {}
        
        # Get raw wiki source (needed for parsing infobox markup)
        # The wikipedia-api library's page.text is processed, so we need raw source
        try:
            api_url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": page_title,
                "format": "json",
                "formatversion": "2"
            }
            headers = {"User-Agent": USER_AGENT}
            
            rate_limiter.wait_if_needed()  # Rate limit this request too
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            pages = data.get("query", {}).get("pages", [])
            if pages and "revisions" in pages[0]:
                text = pages[0]["revisions"][0]["slots"]["main"]["content"]
            else:
                # Fallback to page.text if API call fails
                text = page.text
        except Exception as e:
            logger.warning(f"Failed to get raw wiki source for {page_title}, using page.text: {e}")
            text = page.text
        
        # Try to find infobox section
        infobox_start = text.find('{{Infobox')
        if infobox_start != -1:
            # Get infobox section (first 5000 chars usually contains it)
            infobox_text = text[infobox_start:infobox_start + 5000]
        else:
            # Fallback: use first part of text
            infobox_text = text[:5000] if len(text) > 5000 else text
        
        birth_date = parse_birth_date(infobox_text)
        birth_location = parse_birth_location(infobox_text)
        
        if not birth_date:
            return {}
        
        # Validate year
        if not (1000 <= birth_date['year'] <= 2100):
            return {}
        
        # Post-process location to remove any remaining template artifacts
        if birth_location:
            # Remove everything from {{ onwards (more aggressive)
            if '{{' in birth_location:
                birth_location = birth_location.split('{{')[0]
            birth_location = re.sub(r',\s*$', '', birth_location)  # Remove trailing comma
            birth_location = birth_location.strip()
            # If location is empty or still contains {{, set to empty
            if not birth_location or '{{' in birth_location:
                birth_location = ""
        
        return {
            'title': page_title,
            'url': page.fullurl,
            'birth_date': birth_date,
            'birth_location': birth_location
        }
    
    except requests.exceptions.RequestException as e:
        if retry_count < 3:
            wait_time = 2 ** retry_count
            logger.warning(f"Request error for {page_title}, retrying in {wait_time}s...")
            time.sleep(wait_time)
            return get_infobox_data(page_title, retry_count + 1)
        logger.error(f"Failed to get data for {page_title} after retries: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error getting data for {page_title}: {e}")
        return {}

# ============================================================================
# GET LIST OF FAMOUS PEOPLE
# ============================================================================

def get_famous_people_from_categories() -> List[str]:
    """Get list of famous people from Wikipedia categories."""
    people = []
    
    # Categories with many famous people (prioritize birth century categories - higher success rate)
    categories = [
        "Category:20th-century births",  # Most famous modern people
        "Category:21st-century births",  # Current celebrities
        "Category:19th-century births",  # Historical figures
        "Category:18th-century births",
        "Category:17th-century births",
        "Category:16th-century births",
        "Category:15th-century births",
        "Category:14th-century births",
        "Category:13th-century births",
        "Category:12th-century births",
        "Category:11th-century births",
        "Category:10th-century births",
        "Category:Living people",  # Last resort (very large, lower success rate)
    ]
    
    logger.info("Fetching people from Wikipedia categories...")
    
    for category in categories:
        if len(people) >= 10000:  # Stop if we have enough
            break
        rate_limiter.wait_if_needed()
        try:
            cat = WIKI.page(category)
            if cat.exists():
                # Get category members (limited to avoid too many requests)
                members = list(cat.categorymembers.values())
                count = 0
                for member in members:
                    if member.ns == 0:  # Only main namespace articles
                        people.append(member.title)
                        count += 1
                        if count >= 2000:  # Increased limit per category
                            break
                logger.info(f"Found {count} people in {category} (total: {len(people)})")
        except Exception as e:
            logger.error(f"Error fetching {category}: {e}")
    
    return list(set(people))  # Remove duplicates

def get_famous_people_from_lists() -> List[str]:
    """Get famous people from curated Wikipedia lists."""
    people = []
    
    # Lists that contain many famous people
    list_pages = [
        "List of people by net worth",
        "Time 100",
        "Forbes Celebrity 100",
        "List of Academy Award winners and nominees",
        "List of Nobel laureates",
        "List of Grammy Award winners",
        "List of Emmy Award winners",
    ]
    
    logger.info("Fetching people from Wikipedia lists...")
    
    for list_page in list_pages:
        rate_limiter.wait_if_needed()
        try:
            page = WIKI.page(list_page)
            if page.exists():
                # Extract links from the page (simplified - would need better parsing)
                # For now, this is a placeholder - you'd need to parse the list structure
                logger.info(f"Found list page: {list_page}")
        except Exception as e:
            logger.error(f"Error fetching {list_page}: {e}")
    
    return people

def get_famous_people_from_pageviews(limit: int = 5000) -> List[str]:
    """
    Get top Wikipedia pages by pageviews using Wikimedia Pageviews API.
    Filters for people (has birth date in infobox).
    """
    people = []
    
    logger.info(f"Fetching top {limit} Wikipedia pages by pageviews...")
    
    # Wikimedia Pageviews API endpoint
    # Gets most viewed pages for the last 30 days
    base_url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access"
    
    # Get pages from multiple days to get better coverage
    end_date = date.today() - timedelta(days=1)  # Yesterday
    
    # Use dict to track max views per page (deduplicate across days)
    pages_dict = {}  # {title: max_views}
    
    # Get top pages from last 7 days (to get good coverage)
    for days_ago in range(7):
        target_date = end_date - timedelta(days=days_ago)
        date_str = target_date.strftime("%Y/%m/%d")
        
        rate_limiter.wait_if_needed()
        try:
            url = f"{base_url}/{date_str}"
            headers = {"User-Agent": USER_AGENT}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract page titles
            items = data.get("items", [])
            if items:
                articles = items[0].get("articles", [])
                for article in articles:
                    title = article.get("article", "")
                    views = article.get("views", 0)
                    # Skip non-article pages (File:, Template:, etc.)
                    if ":" not in title:
                        # Keep the maximum views if page appears multiple times
                        if title not in pages_dict or views > pages_dict[title]:
                            pages_dict[title] = views
                
                logger.info(f"Fetched {len(articles)} pages from {date_str} (unique so far: {len(pages_dict)})")
        except Exception as e:
            logger.warning(f"Error fetching pageviews for {date_str}: {e}")
    
    # Convert to list and sort by views (descending)
    all_pages = [(title, views) for title, views in pages_dict.items()]
    all_pages.sort(key=lambda x: x[1], reverse=True)
    
    logger.info(f"Total unique pages after deduplication: {len(all_pages)}")
    
    top_pages = [title for title, views in all_pages[:limit * 3]]  # Get 3x to filter for people
    
    logger.info(f"Found {len(top_pages)} top pages, filtering for people with birth dates...")
    
    # Quick filter: Skip obvious non-person pages BEFORE checking Wikipedia
    skip_patterns = [
        'Main_Page', 'Special:', 'Help:', 'Wikipedia:', 'Template:', 'Category:', 
        'File:', 'MediaWiki:', 'Portal:', 'Talk:', 'User:', 'Project:',
        'List_of_', 'Timeline_of_', 'History_of_', '2026_', '2025_', '2024_',
        'Season_', '_season_', '_(TV_series)', '_(film)', '_(video_game)',
        'Google_Chrome', 'YouTube', 'Facebook', 'Twitter', 'Instagram', 'X_',
        'FIFA_World_Cup', 'Olympic_Games', 'COVID-19', 'Coronavirus'
    ]
    
    filtered_pages = []
    for title in top_pages:
        # Skip if matches any skip pattern
        if any(pattern in title for pattern in skip_patterns):
            continue
        # Skip if starts with number (likely years/events)
        if title and title[0].isdigit():
            continue
        filtered_pages.append(title)
    
    logger.info(f"After quick filter: {len(filtered_pages)} potential people pages (skipped {len(top_pages) - len(filtered_pages)} non-person pages)")
    
    # Filter to only people (those with birth dates AND locations)
    checked = 0
    for page_title in filtered_pages:
        if len(people) >= limit:
            break
        
        if checked % 100 == 0:
            logger.info(f"Checking people: {len(people)}/{limit} found, checked {checked}/{len(filtered_pages)}")
        
        data = get_infobox_data(page_title)
        # Only add if we have BOTH birth_date AND birth_location
        if data and data.get('birth_date') and data.get('birth_location'):
            birth_date = data.get('birth_date', {})
            # Validate birth_date has all required fields
            if birth_date.get('year') and birth_date.get('month') and birth_date.get('day'):
                people.append(page_title)
        
        checked += 1
    
    logger.info(f"Found {len(people)} people from top pageviews")
    return people

def get_famous_people_list(limit: int = 5000) -> List[str]:
    """
    Get a comprehensive list of famous people from multiple sources.
    Prioritizes categories and lists (higher success rate) over pageviews.
    """
    all_people = set()  # Use set to prevent duplicates efficiently
    
    logger.info(f"Building list of up to {limit} famous people...")
    
    # Method 1: Categories (highest success rate - these are guaranteed to be people with birth dates)
    logger.info("Method 1: Fetching from categories (most reliable source)...")
    try:
        category_people = get_famous_people_from_categories()
        all_people.update(category_people)
        logger.info(f"Found {len(category_people)} people from categories (total unique: {len(all_people)})")
    except Exception as e:
        logger.warning(f"Failed to get categories: {e}")
    
    # Method 2: Curated lists (also high success rate)
    if len(all_people) < limit:
        logger.info(f"Method 2: Fetching from curated lists to reach {limit}...")
        try:
            list_people = get_famous_people_from_lists()
            all_people.update(list_people)
            logger.info(f"Found {len(list_people)} people from lists (total unique: {len(all_people)})")
        except Exception as e:
            logger.warning(f"Failed to get lists: {e}")
    
    # Method 3: Top pageviews (lowest success rate, but gets most famous people)
    # Only use if we still need more
    if len(all_people) < limit:
        logger.info(f"Method 3: Fetching top pages by pageviews (to reach {limit})...")
        try:
            # Only get as many as we need
            needed = limit - len(all_people)
            pageview_people = get_famous_people_from_pageviews(limit=needed + 500)  # Get extra buffer
            all_people.update(pageview_people)
            logger.info(f"Found {len(pageview_people)} people from pageviews (total unique: {len(all_people)})")
        except Exception as e:
            logger.warning(f"Failed to get pageviews: {e}")
    
    # Convert to list and limit
    unique_people = list(all_people)
    logger.info(f"Final list: {len(unique_people)} unique people")
    return unique_people[:limit]

# ============================================================================
# CHART CALCULATION
# ============================================================================

def geocode_location(location: str) -> Optional[Dict]:
    """Geocode location using OpenCage API."""
    if not OPENCAGE_KEY:
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
            return None
        
        # Validate required birth date fields
        year = birth_date.get('year')
        month = birth_date.get('month')
        day = birth_date.get('day')
        
        if not year or not month or not day:
            return None
        
        hour = birth_date.get('hour', 12)
        minute = birth_date.get('minute', 0)
        unknown_time = birth_date.get('hour') is None
        
        # Validate birth location exists and is not empty
        location = person_data.get('birth_location', '').strip()
        if not location:
            return None
        
        # Try to geocode location
        geo = geocode_location(location)
        if not geo or not geo.get('lat') or not geo.get('lng'):
            return None
        
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
        
        numerology_raw = calculate_numerology(day, month, year)
        numerology = {
            "life_path_number": numerology_raw.get("life_path", "N/A"),
            "day_number": numerology_raw.get("day_number", "N/A"),
            "lucky_number": numerology_raw.get("lucky_number", "N/A")
        }
        
        chinese_zodiac = get_chinese_zodiac_and_element(year, month, day)
        
        chart_data = chart.get_full_chart_data(
            numerology=numerology,
            name_numerology=None,
            chinese_zodiac=chinese_zodiac,
            unknown_time=unknown_time
        )
        
        elements = extract_chart_elements(chart_data)
        
        return {
            'chart_data': chart_data,
            'elements': elements,
            'unknown_time': unknown_time
        }
    except Exception as e:
        logger.error(f"Error calculating chart for {person_data.get('name')}: {e}")
        return None

# ============================================================================
# MAIN PROCESS
# ============================================================================

def main():
    """Main function to scrape and calculate charts for 5000 people."""
    output_file = open("full_process_output.txt", "w", encoding="utf-8")
    
    def log_print(msg):
        print(msg)
        output_file.write(str(msg) + "\n")
        output_file.flush()
    
    log_print("=" * 70)
    log_print("FULL PROCESS: Scrape 5000 Wikipedia People & Calculate Charts")
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
        
        # Step 1: Get list of famous people (only get as many as we need)
        log_print(f"\n2. Getting list of famous people from Wikipedia...")
        people_list = get_famous_people_list(limit=remaining_needed + 100)  # Get a bit extra in case some fail
        log_print(f"   Found {len(people_list)} potential people")
        
        if not people_list:
            log_print("ERROR: No people found. Check your internet connection and Wikipedia API access.")
            return
        
        # Step 2: Scrape data (with progress saving)
        log_print(f"\n3. Scraping birth data for {len(people_list)} people...")
        log_print(f"   Rate limit: 100 requests/minute (~0.6 seconds between requests)")
        log_print(f"   Estimated time: ~{len(people_list) * 0.6 / 60:.1f} minutes")
        log_print(f"   Progress will be saved to 'scraped_data_backup.json' every 100 people")
        
        # Try to load existing backup if resuming
        backup_file = "scraped_data_backup.json"
        scraped_data = []
        start_idx = 0
        scraped_names = set()  # Track names to prevent duplicates
        
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    scraped_data = json.load(f)
                # Build set of already scraped names
                scraped_names = {item.get('title', '') for item in scraped_data if item.get('title')}
                start_idx = len(scraped_data)
                log_print(f"   Found backup file with {len(scraped_data)} people. Resuming from index {start_idx}...")
            except Exception as e:
                log_print(f"   Could not load backup file: {e}. Starting fresh.")
        
        processed = len(scraped_data)
        skipped = 0
        duplicates_skipped = 0
        
        try:
            for idx, page_title in enumerate(people_list[start_idx:], start=start_idx + 1):
                # Check if we've reached the target (accounting for what's already in DB)
                current_db_count = db.query(FamousPerson).count()
                if current_db_count + len(scraped_data) >= MAX_PEOPLE:
                    log_print(f"\n   ✓ Reached target! Database has {current_db_count}, scraped {len(scraped_data)} new = {current_db_count + len(scraped_data)} total")
                    log_print(f"   Stopping scraping early...")
                    break
                
                if idx % 100 == 0:
                    log_print(f"   Progress: {idx}/{len(people_list)} ({processed} with birth dates, {skipped} skipped, {duplicates_skipped} duplicates)")
                    # Save backup every 100 people
                    try:
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            json.dump(scraped_data, f, indent=2, ensure_ascii=False)
                        log_print(f"   ✓ Backup saved: {len(scraped_data)} people")
                    except Exception as e:
                        log_print(f"   ⚠ Could not save backup: {e}")
                
                # Skip if already scraped (duplicate prevention)
                if page_title in scraped_names:
                    duplicates_skipped += 1
                    continue
                
                data = get_infobox_data(page_title)
                
                # Only add if we have both birth_date AND birth_location
                if data and data.get('birth_date') and data.get('birth_location'):
                    # Validate birth_date has required fields
                    birth_date = data.get('birth_date', {})
                    if birth_date.get('year') and birth_date.get('month') and birth_date.get('day'):
                        scraped_data.append(data)
                        scraped_names.add(page_title)  # Track this name
                        processed += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
        except KeyboardInterrupt:
            log_print(f"\n   ⚠ INTERRUPTED by user. Saving progress...")
            try:
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(scraped_data, f, indent=2, ensure_ascii=False)
                log_print(f"   ✓ Progress saved: {len(scraped_data)} people in {backup_file}")
                log_print(f"   You can resume by running the script again (it will auto-detect the backup)")
            except Exception as e:
                log_print(f"   ✗ Could not save backup: {e}")
            raise
        except Exception as e:
            log_print(f"\n   ⚠ ERROR during scraping: {e}")
            log_print(f"   Saving progress before exit...")
            try:
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(scraped_data, f, indent=2, ensure_ascii=False)
                log_print(f"   ✓ Progress saved: {len(scraped_data)} people in {backup_file}")
            except Exception as save_error:
                log_print(f"   ✗ Could not save backup: {save_error}")
            raise
        
        log_print(f"\n   Scraping complete: {processed} with complete data, {skipped} skipped (missing data), {duplicates_skipped} duplicates")
        
        # Final save of scraped data
        try:
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, indent=2, ensure_ascii=False)
            log_print(f"   ✓ Final backup saved: {len(scraped_data)} people")
        except Exception as e:
            log_print(f"   ⚠ Could not save final backup: {e}")
        
        # Step 3: Calculate charts
        log_print(f"\n4. Calculating charts for {len(scraped_data)} people...")
        log_print(f"   (People without usable data have already been filtered out)")
        
        # Pre-load all existing names from database to avoid duplicate queries
        existing_names = {row[0] for row in db.query(FamousPerson.name).all()}
        log_print(f"   Found {len(existing_names)} people already in database (will skip)")
        
        db_processed = 0
        db_skipped = 0
        db_errors = 0
        
        for idx, person_data in enumerate(scraped_data, 1):
            # Check if we've reached the target
            current_db_count = db.query(FamousPerson).count()
            if current_db_count >= MAX_PEOPLE:
                log_print(f"\n   ✓ Database now has {current_db_count} people (target: {MAX_PEOPLE})")
                log_print(f"   Stopping chart calculation early...")
                break
            
            name = person_data.get('title', '')
            if not name:
                db_errors += 1
                continue
            
            # Check if already exists (using pre-loaded set for faster lookup)
            if name in existing_names:
                db_skipped += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(scraped_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
                continue
            
            # Double-check database (in case of race condition)
            existing = db.query(FamousPerson).filter(FamousPerson.name == name).first()
            if existing:
                existing_names.add(name)  # Add to set for future iterations
                db_skipped += 1
                if idx % 50 == 0:
                    log_print(f"   Progress: {idx}/{len(scraped_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
                continue
            
            if idx % 50 == 0:
                log_print(f"   Progress: {idx}/{len(scraped_data)} (processed: {db_processed}, skipped: {db_skipped}, errors: {db_errors})")
            
            # Validate data before calculating
            birth_date = person_data.get('birth_date', {})
            birth_location = person_data.get('birth_location', '')
            
            if not birth_date or not birth_location:
                db_errors += 1
                continue
            
            if not (birth_date.get('year') and birth_date.get('month') and birth_date.get('day')):
                db_errors += 1
                continue
            
            chart_result = calculate_person_chart(person_data)
            if not chart_result:
                db_errors += 1
                continue
            
            # Add to existing_names set to prevent duplicates in same run
            existing_names.add(name)
            
            # Extract numerology and Chinese zodiac
            numerology_data = chart_result['chart_data'].get('numerology_analysis', {})
            chinese_zodiac_str = chart_result['chart_data'].get('chinese_zodiac', '')
            
            chinese_animal = None
            chinese_element = None
            if chinese_zodiac_str and isinstance(chinese_zodiac_str, str) and chinese_zodiac_str != 'N/A':
                parts = chinese_zodiac_str.strip().split()
                if len(parts) >= 2:
                    chinese_element = parts[0]
                    chinese_animal = parts[1]
            
            birth_date = person_data.get('birth_date', {})
            famous_person = FamousPerson(
                name=name,
                wikipedia_url=person_data.get('url', ''),
                occupation=None,  # Could extract from infobox if needed
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
            db_processed += 1
            
            # Commit in batches (saves progress every 50 people)
            if db_processed % BATCH_SIZE == 0:
                try:
                    db.commit()
                    log_print(f"   ✓ Committed batch: {db_processed} people saved to database")
                except Exception as e:
                    log_print(f"   ✗ Error committing batch: {e}")
                    db.rollback()
                    raise
        
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
        log_print(f"Scraped: {processed} people with birth dates")
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

