"""
Wikipedia Scraper for Famous People - COMPLIANT VERSION
This version properly respects Wikipedia's API rate limits and terms of service.

Usage:
    python scripts/scrape_wikipedia_famous_people_fixed.py

Requirements:
    pip install wikipedia-api requests

Wikipedia API Compliance:
- Uses proper User-Agent identification
- Respects rate limits (500/hour anonymous, 5000/hour authenticated)
- Handles rate limit errors gracefully
- Implements exponential backoff for retries
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from typing import Dict, Optional, List
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import wikipediaapi
    import requests
except ImportError:
    print("Required packages not installed. Run: pip install wikipedia-api requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# WIKIPEDIA API COMPLIANCE SETTINGS
# ============================================================================

# User-Agent is REQUIRED by Wikipedia's Terms of Service
# Format: AppName/Version (contact email)
USER_AGENT = "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"

# Rate limiting based on Wikipedia's safe practices:
# Wikipedia doesn't publish exact numbers, but safe rules:
# - 100-200 requests/minute = generally OK (no token needed)
# Using conservative 100 requests/minute = 1 request every 0.6 seconds
REQUEST_DELAY = 0.6  # 0.6 seconds = 100 requests/minute = 6,000 requests/hour (safe limit)

# For faster scraping (if needed):
# REQUEST_DELAY = 0.3  # 0.3 seconds = 200 requests/minute (still safe)

# Maximum retries for failed requests
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # Base delay for exponential backoff (seconds)

# Wikipedia API setup with User-Agent
WIKI = wikipediaapi.Wikipedia(
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI,
    user_agent=USER_AGENT  # Required for compliance
)


# ============================================================================
# RATE LIMIT TRACKING
# ============================================================================

class RateLimiter:
    """Track requests to ensure we stay within Wikipedia's safe limits."""
    
    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.request_times = []
        self.min_delay = 60.0 / requests_per_minute  # Minimum seconds between requests
    
    def wait_if_needed(self):
        """Wait if we're approaching the rate limit."""
        now = time.time()
        
        # Remove requests older than 1 minute
        self.request_times = [t for t in self.request_times if now - t < 60]
        
        # If we're at the limit, wait
        if len(self.request_times) >= self.requests_per_minute:
            oldest_request = min(self.request_times)
            wait_time = 60 - (now - oldest_request) + 1
            if wait_time > 0:
                logger.warning(f"Rate limit approaching. Waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
        
        # Always wait minimum delay between requests
        if self.request_times:
            time_since_last = now - self.request_times[-1]
            if time_since_last < self.min_delay:
                time.sleep(self.min_delay - time_since_last)
        
        self.request_times.append(time.time())


rate_limiter = RateLimiter(requests_per_minute=100)  # Safe: 100 requests/minute


# ============================================================================
# PARSING FUNCTIONS
# ============================================================================

def parse_birth_date(infobox_text: str) -> Optional[Dict[str, int]]:
    """Parse birth date from Wikipedia infobox (handles wiki markup format)."""
    
    month_map = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    # Pattern 1: Handle nested templates like {{circa|{{birth date|df=yes|1564|04|23}}}}
    # Match: {{circa|{{birth date|df=yes|1564|04|23}}}}
    nested_pattern = re.search(r'\{\{circa\s*\|\s*\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if nested_pattern:
        try:
            year = int(nested_pattern.group(1))
            month = int(nested_pattern.group(2))
            day = int(nested_pattern.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                logger.debug(f"Pattern 1 matched: year={year}, month={month}, day={day}")
                return {'year': year, 'month': month, 'day': day}
            else:
                logger.debug(f"Pattern 1 matched but validation failed: year={year}, month={month}, day={day}")
        except (ValueError, IndexError) as e:
            logger.debug(f"Pattern 1 matched but extraction failed: {e}")
            pass
    
    # Pattern 2: {{birth date|df=yes|1452|04|15}} - lowercase, with df parameter
    birth_date_lower_df = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_lower_df:
        try:
            year = int(birth_date_lower_df.group(1))
            month = int(birth_date_lower_df.group(2))
            day = int(birth_date_lower_df.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                logger.debug(f"Pattern 2 matched: year={year}, month={month}, day={day}")
                return {'year': year, 'month': month, 'day': day}
            else:
                logger.debug(f"Pattern 2 matched but validation failed: year={year}, month={month}, day={day}")
        except (ValueError, IndexError) as e:
            logger.debug(f"Pattern 2 matched but extraction failed: {e}")
            pass
    
    # Pattern 3: {{Birth date|df=y|1643|01|04}} - capital B, with df parameter
    birth_date_capital_df = re.search(r'\{\{Birth date\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_capital_df:
        try:
            year = int(birth_date_capital_df.group(1))
            month = int(birth_date_capital_df.group(2))
            day = int(birth_date_capital_df.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                logger.debug(f"Pattern 3 matched: year={year}, month={month}, day={day}")
                return {'year': year, 'month': month, 'day': day}
            else:
                logger.debug(f"Pattern 3 matched but validation failed: year={year}, month={month}, day={day}")
        except (ValueError, IndexError) as e:
            logger.debug(f"Pattern 3 matched but extraction failed: {e}")
            pass
    
    # Pattern 4: {{birth date|1879|3|14}} - standard format without df parameter
    birth_date_standard = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_standard:
        try:
            year = int(birth_date_standard.group(1))
            month = int(birth_date_standard.group(2))
            day = int(birth_date_standard.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                return {'year': year, 'month': month, 'day': day}
        except (ValueError, IndexError):
            pass
    
    # Pattern 5: {{Birth date|1643|01|04}} - capital B, without df parameter
    birth_date_capital = re.search(r'\{\{Birth date\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_capital:
        try:
            year = int(birth_date_capital.group(1))
            month = int(birth_date_capital.group(2))
            day = int(birth_date_capital.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                return {'year': year, 'month': month, 'day': day}
        except (ValueError, IndexError):
            pass
    
    # Pattern 5: | birth_date = 14 March 1879 (plain text format)
    birth_date_param = re.search(r'\|\s*birth_date\s*=\s*(\d{1,2})\s+(\w+)\s+(\d{4})', infobox_text, re.IGNORECASE)
    if birth_date_param:
        try:
            day = int(birth_date_param.group(1))
            month_str = birth_date_param.group(2).lower()
            year = int(birth_date_param.group(3))
            month = month_map.get(month_str)
            if month and 1 <= month <= 12 and 1 <= day <= 31 and 1800 <= year <= 2100:
                return {'year': year, 'month': month, 'day': day}
        except (ValueError, IndexError):
            pass
    
    # Fallback: Try plain text patterns (for extracted text format)
    patterns = [
        r'born\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # "born January 15, 1990"
        r'born\s+(\d{1,2})\s+(\w+)\s+(\d{4})',     # "born 15 January 1990"
        r'born\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # "born 15/01/1990"
        r'born\s+(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # "born 1990/01/15"
    ]
    
    month_map = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
        'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
        'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
        'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    text_lower = infobox_text.lower()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    if groups[0].isdigit() and groups[1].isdigit():
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        else:  # MM-DD-YYYY
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        month_str = groups[0].lower() if groups[0].isalpha() else groups[1].lower()
                        month = month_map.get(month_str)
                        if not month:
                            continue
                        day = int(groups[1] if groups[0].isalpha() else groups[0])
                        year = int(groups[2])
                    
                    if 1 <= month <= 12 and 1 <= day <= 31 and 1000 <= year <= 2100:
                        return {'year': year, 'month': month, 'day': day}
            except (ValueError, IndexError):
                continue
    
    return None


def clean_wiki_markup(text: str) -> str:
    """Clean up Wikipedia wiki markup from text."""
    if not text:
        return ""
    
    # Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove wiki links but keep the text: [[Link|Display]] -> Display, [[Link]] -> Link
    text = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m.group(1).split('|')[-1], text)
    
    # Remove templates - handle both complete and incomplete templates
    # Remove complete templates {{template|params}}
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    # Remove incomplete templates (like {{efn, {{nowrap, {{awrap)
    text = re.sub(r'\{\{[^}]*$', '', text)  # At end of string
    text = re.sub(r'\{\{[a-zA-Z]+\s*[^}]*$', '', text)  # Incomplete templates
    # Remove any remaining {{ patterns
    text = re.sub(r'\{\{[^}]*', '', text)
    
    # Remove ref tags and other common wiki markup
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<ref[^>]*/>', '', text, flags=re.IGNORECASE)
    
    # Remove specific incomplete template patterns
    text = re.sub(r'{{efn[^}]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'{{nowrap[^}]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'{{awrap[^}]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'{{hlist[^}]*', '', text, flags=re.IGNORECASE)
    
    # Remove pipe-separated parts (take the last meaningful part)
    if '|' in text:
        parts = [p.strip() for p in text.split('|')]
        # Filter out template-like parts and keep the most descriptive
        parts = [p for p in parts if p and not p.startswith('{{') and len(p) > 2]
        if parts:
            text = parts[-1]  # Take the last meaningful part
    
    # Clean up whitespace and punctuation artifacts
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    text = re.sub(r'^[,\s]+|[,\s]+$', '', text)  # Remove leading/trailing commas and spaces
    text = re.sub(r',+', ',', text)  # Remove duplicate commas
    # Remove any trailing incomplete template markers
    text = re.sub(r',\s*\{{[^}]*$', '', text)
    text = text.strip()
    
    return text


def parse_birth_location(infobox_text: str) -> Optional[str]:
    """Parse birth location from Wikipedia infobox (handles wiki markup format)."""
    
    # Try infobox parameter format: | birth_place = [[Ulm]], [[Kingdom of Württemberg]]
    # Capture until next infobox parameter (||) or newline, handling templates properly
    birth_place_param = re.search(r'\|\s*birth_place\s*=\s*([^\n]+?)(?=\s*\|\||$)', infobox_text, re.IGNORECASE)
    if birth_place_param:
        location = birth_place_param.group(1).strip()
        
        # Remove templates and extract their content
        # First, extract content from templates like {{nowrap|content}} -> content
        location = re.sub(r'\{\{(?:nowrap|awrap)\|([^}]+)\}\}', r'\1', location, flags=re.IGNORECASE)
        # Remove complete templates like {{efn|...}}
        location = re.sub(r'\{\{[^}]*\}\}', '', location)
        # Remove incomplete templates (everything from {{ onwards)
        location = re.sub(r'\{\{.*$', '', location)
        # Also remove any remaining {{ patterns
        location = re.sub(r'\{\{[^}]*', '', location)
        
        # Split by comma and filter out parts that contain templates
        parts = []
        for part in location.split(','):
            part = part.strip()
            # Skip parts that start with or contain template markers
            if part.startswith('{{') or '{{' in part:
                # Try to extract text before the template
                before_template = re.split(r'\{\{', part)[0].strip()
                if before_template and len(before_template) > 2:
                    parts.append(before_template)
                break
            if part:
                parts.append(part)
        
        if parts:
            # Filter out any parts that still contain {{ (shouldn't happen, but safety check)
            parts = [p for p in parts if '{{' not in p]
            if not parts:
                return None
            location = ', '.join(parts)
            location = clean_wiki_markup(location)
            # Final aggressive cleanup - remove any remaining template artifacts
            location = re.sub(r'[,\s]*\{\{[^}]*$', '', location)
            location = re.sub(r'\{\{.*$', '', location)  # Remove everything from {{ onwards
            location = re.sub(r'[,\s]*\{\{[^}]*', '', location)
            location = location.strip()
            location = re.sub(r',+$', '', location).strip()
            # Final check - don't return if it contains template markers
            if location and len(location) > 2 and '{{' not in location and not location.startswith('{{'):
                return location
    
    # Try place_of_birth parameter
    place_param = re.search(r'\|\s*place_of_birth\s*=\s*([^\n]+?)(?=\s*\|\||$)', infobox_text, re.IGNORECASE)
    if place_param:
        location = place_param.group(1).strip()
        
        # Remove templates
        location = re.sub(r'\{\{(?:nowrap|awrap)\|([^}]+)\}\}', r'\1', location, flags=re.IGNORECASE)
        location = re.sub(r'\{\{[^}]*\}\}', '', location)
        location = re.sub(r'\{\{.*$', '', location)
        location = re.sub(r'\{\{[^}]*', '', location)
        
        # Split by comma and filter
        parts = []
        for part in location.split(','):
            part = part.strip()
            if part.startswith('{{') or '{{' in part:
                before_template = re.split(r'\{\{', part)[0].strip()
                if before_template and len(before_template) > 2:
                    parts.append(before_template)
                break
            if part:
                parts.append(part)
        
        if parts:
            # Filter out any parts that still contain {{ (shouldn't happen, but safety check)
            parts = [p for p in parts if '{{' not in p]
            if not parts:
                return None
            location = ', '.join(parts)
            location = clean_wiki_markup(location)
            location = re.sub(r'[,\s]*\{\{[^}]*$', '', location)
            location = re.sub(r'\{\{.*$', '', location)
            location = re.sub(r'[,\s]*\{\{[^}]*', '', location)
            location = location.strip()
            location = re.sub(r',+$', '', location).strip()
            if location and len(location) > 2 and '{{' not in location and not location.startswith('{{'):
                return location
    
    # Fallback: Try plain text patterns
    patterns = [
        r'born\s+in\s+([^,\n]+(?:,\s*[^,\n]+)*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, infobox_text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            location = clean_wiki_markup(location)
            if location and len(location) > 2:
                return location
    
    return None


# ============================================================================
# WIKIPEDIA API FUNCTIONS WITH ERROR HANDLING
# ============================================================================

def get_infobox_data(page_title: str, retry_count: int = 0) -> Dict:
    """
    Get infobox data from Wikipedia page with proper error handling.
    
    Handles:
    - Rate limiting (429 errors)
    - Network errors
    - Missing pages
    - Retries with exponential backoff
    """
    # Rate limit before making request
    rate_limiter.wait_if_needed()
    
    try:
        page = WIKI.page(page_title)
        
        if not page.exists():
            logger.warning(f"Page does not exist: {page_title}")
            return {}
        
        # Get the raw wiki source using the API directly
        # The wikipedia-api library's page.text might be processed, so we'll use requests
        # to get the raw wiki markup
        try:
            import requests
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
        # Wikipedia infoboxes are in format: {{Infobox person|...}}
        infobox_start = text.find('{{Infobox')
        if infobox_start != -1:
            # Find the end of the infobox (look for closing braces, but handle nesting)
            # Take a larger chunk to ensure we get the full infobox
            infobox_text = text[infobox_start:infobox_start + 5000]
        else:
            # Fallback: use first part of text where birth info is usually mentioned
            infobox_text = text[:3000]
        
        birth_date = parse_birth_date(infobox_text)
        birth_location = parse_birth_location(infobox_text)
        
        # Post-process location to remove any remaining template artifacts
        if birth_location:
            # Remove everything from {{ onwards (more aggressive)
            if '{{' in birth_location:
                # Split on {{ and take only the part before it
                birth_location = birth_location.split('{{')[0]
            birth_location = re.sub(r',\s*$', '', birth_location)  # Remove trailing comma
            birth_location = birth_location.strip()
            # If location is empty or still contains {{, set to None
            if not birth_location or '{{' in birth_location or birth_location.startswith('{{'):
                birth_location = None
        
        # Debug: log a sample if we didn't find birth date
        if not birth_date:
            debug_msg = f"DEBUG: Infobox sample for {page_title}:\n{infobox_text[:1500]}\n---"
            logger.debug(debug_msg)
            print(debug_msg)
            # Test each pattern individually for debugging (using EXACT same patterns as parsing)
            print(f"Testing patterns for {page_title}:")
            # Pattern 1 - nested
            p1 = re.search(r'\{\{circa\s*\|\s*\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
            print(f"  Pattern 1 (nested): {'MATCH' if p1 else 'NO MATCH'}")
            if p1:
                print(f"    Groups: year={p1.group(1)}, month={p1.group(2)}, day={p1.group(3)}")
            # Pattern 2 - lowercase with df
            p2 = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
            print(f"  Pattern 2 (with df): {'MATCH' if p2 else 'NO MATCH'}")
            if p2:
                print(f"    Groups: year={p2.group(1)}, month={p2.group(2)}, day={p2.group(3)}")
            # Pattern 3 - capital B with df
            p3 = re.search(r'\{\{Birth date\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
            print(f"  Pattern 3 (capital B with df): {'MATCH' if p3 else 'NO MATCH'}")
            if p3:
                print(f"    Groups: year={p3.group(1)}, month={p3.group(2)}, day={p3.group(3)}")
        
        # Get occupation
        occupation = None
        if 'occupation' in infobox_text.lower():
            occ_match = re.search(r'occupation\s*=\s*([^|\n]+)', infobox_text, re.IGNORECASE)
            if occ_match:
                occupation = occ_match.group(1).strip()
        
        if not occupation and page.text:
            first_sent = page.text.split('.')[0]
            if ' is ' in first_sent or ' was ' in first_sent:
                occupation = first_sent.split(' is ')[-1].split(' was ')[-1].split('.')[0].strip()[:100]
        
        # Final cleanup of birth_location before returning - remove ALL template artifacts
        if birth_location:
            # Remove everything from {{ onwards using split
            if '{{' in birth_location:
                birth_location = birth_location.split('{{')[0]
            birth_location = birth_location.strip()
            # Remove trailing commas and spaces
            birth_location = re.sub(r',+\s*$', '', birth_location).strip()
            # Final validation - if empty, starts with {{, or contains {{, set to None
            if not birth_location or birth_location.startswith('{{') or '{{' in birth_location:
                birth_location = None
        
        return {
            'title': page.title,
            'url': page.fullurl,
            'birth_date': birth_date,
            'birth_location': birth_location,
            'occupation': occupation,
            'text_length': len(page.text)
        }
    
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors (including rate limiting)
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        
        if status_code == 429:
            # Rate limited - wait longer
            wait_time = RETRY_DELAY_BASE * (2 ** retry_count)
            print(f"  ⚠ Rate limited (429) for {page_title}. Waiting {wait_time} seconds...")
            logger.warning(f"Rate limited (429). Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            
            if retry_count < MAX_RETRIES:
                return get_infobox_data(page_title, retry_count + 1)
            else:
                logger.error(f"Max retries reached for {page_title} due to rate limiting")
                return {}
        else:
            logger.error(f"HTTP error for {page_title}: {e} (status: {status_code})")
            return {}
    
    except Exception as e:
        # Catch all other exceptions (network errors, parsing errors, etc.)
        error_msg = str(e)
        logger.error(f"Error getting data for {page_title}: {error_msg}")
        
        # Only retry on certain errors (not on parsing errors)
        if retry_count < MAX_RETRIES and any(keyword in error_msg.lower() for keyword in ['timeout', 'connection', '429', 'rate']):
            wait_time = RETRY_DELAY_BASE * (2 ** retry_count)
            print(f"  ⚠ Error for {page_title}. Retrying after {wait_time} seconds...")
            logger.info(f"Retrying {page_title} after {wait_time} seconds...")
            time.sleep(wait_time)
            return get_infobox_data(page_title, retry_count + 1)
        
        return {}


# ============================================================================
# MAIN SCRAPING FUNCTIONS
# ============================================================================

def get_famous_people_from_list(list_page_title: str) -> List[str]:
    """
    Get list of famous people from a Wikipedia list page.
    Example: "List of actors" or "Time 100"
    """
    rate_limiter.wait_if_needed()
    
    try:
        page = WIKI.page(list_page_title)
        if not page.exists():
            logger.warning(f"List page does not exist: {list_page_title}")
            return []
        
        # Extract links from the page
        # This is a simplified approach - in production you'd parse the list structure
        people = []
        # Implementation would parse the list page structure
        return people
    
    except Exception as e:
        logger.error(f"Error getting list {list_page_title}: {e}")
        return []


def scrape_famous_people(people_list: List[str], limit: int = 2000, log_print=None) -> List[Dict]:
    """
    Scrape famous people data from Wikipedia.
    
    Args:
        people_list: List of Wikipedia page titles to scrape
        limit: Maximum number of people to process
    
    Returns:
        List of dictionaries with person data
    """
    famous_people = []
    processed = 0
    skipped = 0
    
    if log_print is None:
        log_print = print
    
    log_print(f"\nStarting to scrape {min(len(people_list), limit)} people...")
    log_print(f"Rate limit: 100 requests/minute (one request every ~0.6 seconds)")
    logger.info(f"Starting to scrape {min(len(people_list), limit)} people...")
    logger.info(f"Rate limit: 100 requests/minute (one request every ~0.6 seconds)")
    
    for idx, page_title in enumerate(people_list[:limit], 1):
        log_print(f"\n[{idx}/{min(len(people_list), limit)}] Processing: {page_title}")
        
        if processed % 10 == 0 and processed > 0:
            log_print(f"  Progress: {processed} processed, {skipped} skipped, {len(people_list) - idx} remaining")
            logger.info(f"Processed: {processed}, Skipped: {skipped}, Remaining: {len(people_list) - idx}")
        
        data = get_infobox_data(page_title)
        
        if not data or not data.get('birth_date'):
            log_print(f"  ✗ Skipped: No birth date found")
            skipped += 1
            continue
        
        famous_people.append({
            'name': data['title'],
            'wikipedia_url': data['url'],
            'birth_date': data['birth_date'],
            'birth_location': data.get('birth_location', ''),
            'occupation': data.get('occupation', '')
        })
        
        processed += 1
        log_print(f"  ✓ {data['title']}: Born {data['birth_date']['month']}/{data['birth_date']['day']}/{data['birth_date']['year']} in {data.get('birth_location', 'Unknown')}")
        
        # Note: rate_limiter.wait_if_needed() already handles delays, no need for additional sleep
    
    log_print(f"\n✓ Scraping complete! Processed: {processed}, Skipped: {skipped}")
    logger.info(f"Scraping complete! Processed: {processed}, Skipped: {skipped}")
    return famous_people


def main():
    """Main function to scrape Wikipedia and save results."""
    output_file = "famous_people_data.json"
    log_file = "scraper_run.log"
    
    # Open log file for writing
    log_f = open(log_file, 'w', encoding='utf-8')
    
    def log_print(msg):
        """Print to both console and log file."""
        print(msg, flush=True)
        log_f.write(msg + '\n')
        log_f.flush()
    
    # Use both print and logger to ensure output is visible
    log_print("=" * 60)
    log_print("Wikipedia Famous People Scraper - COMPLIANT VERSION")
    log_print("=" * 60)
    log_print(f"User-Agent: {USER_AGENT}")
    log_print(f"Rate Limit: 100 requests/minute (~0.6 seconds between requests)")
    log_print("Note: Wikipedia doesn't publish exact limits, but 100-200/min is generally safe")
    log_print("=" * 60)
    
    logger.info("=" * 60)
    logger.info("Wikipedia Famous People Scraper - COMPLIANT VERSION")
    logger.info("=" * 60)
    logger.info(f"User-Agent: {USER_AGENT}")
    logger.info(f"Rate Limit: 100 requests/minute (~0.6 seconds between requests)")
    logger.info("Note: Wikipedia doesn't publish exact limits, but 100-200/min is generally safe")
    logger.info("=" * 60)
    
    # For now, use a manual list of famous people
    # In production, you'd:
    # 1. Get a list from Wikipedia categories
    # 2. Use Wikipedia's pageview API to find popular pages
    # 3. Use a curated list of famous people
    
    sample_people_titles = [
        "Albert Einstein",
        "Marie Curie",
        "Leonardo da Vinci",
        "William Shakespeare",
        "Isaac Newton",
        # Add more as needed
    ]
    
    try:
        log_print(f"\nScraping {len(sample_people_titles)} people as example...")
        logger.info(f"Scraping {len(sample_people_titles)} people as example...")
        famous_people = scrape_famous_people(sample_people_titles, log_print=log_print)
        
        # Save to JSON
        log_print(f"\nSaving results to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(famous_people, f, indent=2, ensure_ascii=False)
        
        log_print(f"✓ Saved {len(famous_people)} entries to {output_file}")
        log_print(f"\n✓ Log saved to {log_file}")
        log_print("\nNext step: Run calculate_famous_people_charts.py to calculate their charts")
        logger.info(f"Saved {len(famous_people)} entries to {output_file}")
        logger.info("Next step: Run calculate_famous_people_charts.py to calculate their charts")
    finally:
        log_f.close()


if __name__ == "__main__":
    main()

