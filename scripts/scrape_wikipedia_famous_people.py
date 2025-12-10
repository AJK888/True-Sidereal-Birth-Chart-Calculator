"""
Wikipedia Scraper for Famous People
Scrapes Wikipedia for top individuals and extracts birth date/location information.

Usage:
    python scripts/scrape_wikipedia_famous_people.py

Requirements:
    pip install wikipedia-api beautifulsoup4 requests
"""

import os
import sys
import time
import json
import re
from datetime import datetime
from typing import Dict, Optional, List
import logging

# Add parent directory to path to import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import wikipediaapi
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages not installed. Run: pip install wikipedia-api beautifulsoup4 requests")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Wikipedia API setup
WIKI = wikipediaapi.Wikipedia('en', extract_format=wikipediaapi.ExtractFormat.WIKI)

# Rate limiting
# Wikipedia doesn't publish exact numbers, but safe rules:
# 100-200 requests/minute = generally OK (no token needed)
REQUEST_DELAY = 0.6  # 0.6 seconds = 100 requests/minute (safe, conservative)
# Can use 0.3 seconds for 200 requests/minute if needed


def parse_birth_date(infobox_text: str) -> Optional[Dict[str, int]]:
    """
    Parse birth date from Wikipedia infobox.
    Returns dict with year, month, day or None if not found.
    """
    # Common patterns for birth dates
    patterns = [
        r'born\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # "born January 15, 1990"
        r'born\s+(\d{1,2})\s+(\w+)\s+(\d{4})',     # "born 15 January 1990"
        r'born\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # "born 15/01/1990"
        r'born\s+(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # "born 1990/01/15"
    ]
    
    month_map = {
        'january': 1, 'jan': 1,
        'february': 2, 'feb': 2,
        'march': 3, 'mar': 3,
        'april': 4, 'apr': 4,
        'may': 5,
        'june': 6, 'jun': 6,
        'july': 7, 'jul': 7,
        'august': 8, 'aug': 8,
        'september': 9, 'sep': 9, 'sept': 9,
        'october': 10, 'oct': 10,
        'november': 11, 'nov': 11,
        'december': 12, 'dec': 12
    }
    
    text_lower = infobox_text.lower()
    
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    # Try to determine format
                    if groups[0].isdigit() and groups[1].isdigit():
                        # Numeric format
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year = int(groups[0])
                            month = int(groups[1])
                            day = int(groups[2])
                        else:  # DD-MM-YYYY or MM-DD-YYYY
                            # Assume MM-DD-YYYY for US format
                            month = int(groups[0])
                            day = int(groups[1])
                            year = int(groups[2])
                    else:
                        # Text month format
                        month_str = groups[0].lower() if groups[0].isalpha() else groups[1].lower()
                        month = month_map.get(month_str)
                        if not month:
                            continue
                        day = int(groups[1] if groups[0].isalpha() else groups[0])
                        year = int(groups[2])
                    
                    if 1 <= month <= 12 and 1 <= day <= 31 and 1800 <= year <= 2100:
                        return {'year': year, 'month': month, 'day': day}
            except (ValueError, IndexError):
                continue
    
    return None


def parse_birth_location(infobox_text: str) -> Optional[str]:
    """Parse birth location from Wikipedia infobox."""
    patterns = [
        r'born\s+in\s+([^,\n]+(?:,\s*[^,\n]+)*)',
        r'birth_place\s*=\s*([^|\n]+)',
        r'place_of_birth\s*=\s*([^|\n]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, infobox_text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up common Wikipedia formatting
            location = re.sub(r'\[\[([^\]]+)\]\]', r'\1', location)  # Remove [[links]]
            location = re.sub(r'<[^>]+>', '', location)  # Remove HTML tags
            location = location.split('|')[-1]  # Take last part if pipe-separated
            if location and len(location) > 2:
                return location.strip()
    
    return None


def get_infobox_data(page_title: str) -> Dict:
    """Get infobox data from Wikipedia page."""
    try:
        page = WIKI.page(page_title)
        if not page.exists():
            return {}
        
        # Get full page text
        text = page.text
        
        # Try to find infobox section
        infobox_match = re.search(r'\{\{Infobox[^}]+\}\}', text, re.DOTALL)
        if infobox_match:
            infobox_text = infobox_match.group(0)
        else:
            infobox_text = text[:2000]  # Use first part of text
        
        birth_date = parse_birth_date(infobox_text)
        birth_location = parse_birth_location(infobox_text)
        
        # Try to get occupation from infobox or first sentence
        occupation = None
        if 'occupation' in infobox_text.lower():
            occ_match = re.search(r'occupation\s*=\s*([^|\n]+)', infobox_text, re.IGNORECASE)
            if occ_match:
                occupation = occ_match.group(1).strip()
        
        if not occupation and page.text:
            # Try to extract from first sentence
            first_sent = page.text.split('.')[0]
            if ' is ' in first_sent or ' was ' in first_sent:
                occupation = first_sent.split(' is ')[-1].split(' was ')[-1].split('.')[0].strip()[:100]
        
        return {
            'title': page.title,
            'url': page.fullurl,
            'birth_date': birth_date,
            'birth_location': birth_location,
            'occupation': occupation,
            'text_length': len(page.text)
        }
    except Exception as e:
        logger.error(f"Error getting data for {page_title}: {e}")
        return {}


def get_top_wikipedia_pages(limit: int = 2000) -> List[str]:
    """
    Get top Wikipedia pages by page views.
    Uses Wikipedia's most viewed pages API.
    """
    logger.info(f"Fetching top {limit} Wikipedia pages...")
    
    # Wikipedia API endpoint for most viewed pages
    # Note: This is a simplified approach. For production, you might want to use
    # Wikipedia's official pageview API or a curated list of famous people.
    
    # Alternative: Use a curated list of famous people categories
    categories = [
        "List of actors",
        "List of musicians",
        "List of writers",
        "List of scientists",
        "List of politicians",
        "List of athletes",
        "List of artists",
        "List of philosophers",
    ]
    
    page_titles = []
    
    # For now, we'll use a manual approach with Wikipedia's category pages
    # In production, you'd want to use the Wikipedia API more systematically
    logger.warning("Using manual category approach. For production, consider using Wikipedia's pageview API.")
    
    return page_titles


def scrape_famous_people_from_categories(limit: int = 2000) -> List[Dict]:
    """
    Scrape famous people from Wikipedia categories.
    This is a more reliable approach than page views.
    """
    famous_people = []
    
    # Categories known to contain famous people
    categories = [
        "Category:Living people",
        "Category:20th-century births",
        "Category:21st-century births",
    ]
    
    # For a more targeted approach, use specific lists
    list_pages = [
        "List of people by net worth",
        "Time 100",
        "Forbes Celebrity 100",
    ]
    
    logger.info("Starting Wikipedia scrape...")
    logger.warning("This script uses a simplified approach. For production, consider:")
    logger.warning("1. Using Wikipedia's official API with proper rate limiting")
    logger.warning("2. Using a curated list of famous people")
    logger.warning("3. Implementing proper error handling and retries")
    
    # Example: Scrape from a specific list page
    # In production, you'd iterate through multiple sources
    
    return famous_people


def main():
    """Main function to scrape Wikipedia and save results."""
    output_file = "famous_people_data.json"
    
    logger.info("Starting Wikipedia famous people scraper...")
    
    # For now, we'll create a sample structure
    # In production, you'd implement the full scraping logic
    
    sample_people = [
        {
            "name": "Albert Einstein",
            "wikipedia_url": "https://en.wikipedia.org/wiki/Albert_Einstein",
            "birth_date": {"year": 1879, "month": 3, "day": 14},
            "birth_location": "Ulm, Kingdom of Württemberg, German Empire",
            "occupation": "Theoretical physicist"
        },
        # Add more manually or implement full scraping
    ]
    
    logger.info(f"Found {len(sample_people)} people (sample data)")
    logger.info("For full implementation, complete the scraping functions above")
    
    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sample_people, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(sample_people)} entries to {output_file}")
    logger.info("Next step: Run calculate_famous_people_charts.py to calculate their charts")


if __name__ == "__main__":
    main()

