"""Update Wikipedia pageviews for all famous people in the database"""

import os
import sys
import time
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-Agent required by Wikimedia API
USER_AGENT = "SynthesisAstrology/1.0 (contact@example.com)"

# Rate limiting: Wikimedia allows 200 requests/second, but be respectful
REQUEST_DELAY = 0.1  # 100ms between requests = 10 requests/second (very safe)

def extract_page_title(wikipedia_url: str) -> Optional[str]:
    """Extract Wikipedia page title from URL."""
    if not wikipedia_url:
        return None
    
    # Handle different URL formats:
    # https://en.wikipedia.org/wiki/Barack_Obama
    # https://en.wikipedia.org/wiki/Barack_Obama?oldid=123456
    # https://en.wikipedia.org/wiki/Barack_Obama#Section
    
    try:
        # Extract the part after /wiki/
        if "/wiki/" in wikipedia_url:
            title_part = wikipedia_url.split("/wiki/")[1]
            # Remove query parameters and fragments
            title_part = title_part.split("?")[0].split("#")[0]
            # URL decode
            title = unquote(title_part).replace("_", " ")
            return title
    except Exception as e:
        logger.warning(f"Error extracting title from {wikipedia_url}: {e}")
    
    return None

def get_pageviews_for_year(page_title: str) -> Optional[int]:
    """
    Get total pageviews for a Wikipedia page over the past year.
    Uses monthly aggregation for efficiency.
    """
    # Convert page title to URL format (spaces to underscores)
    page_title_encoded = page_title.replace(" ", "_")
    
    # Calculate date range (past 12 months)
    end_date = datetime.now() - timedelta(days=1)  # Yesterday (most recent complete day)
    start_date = end_date - timedelta(days=365)  # One year ago
    
    # Format dates for API (YYYYMMDD)
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    
    # Use monthly aggregation for efficiency (faster than daily)
    # API endpoint: /metrics/pageviews/per-article/{project}/{access}/{agent}/{article}/{granularity}/{start}/{end}
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{page_title_encoded}/monthly/{start_str}/{end_str}"
    
    headers = {"User-Agent": USER_AGENT}
    
    try:
        time.sleep(REQUEST_DELAY)  # Rate limiting
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            # Page might not exist or have no views
            logger.debug(f"No pageview data found for {page_title}")
            return 0
        
        # Handle rate limiting (429 Too Many Requests)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            # Retry once
            response = requests.get(url, headers=headers, timeout=15)
        
        response.raise_for_status()
        data = response.json()
        
        # Sum up all monthly views
        total_views = 0
        items = data.get("items", [])
        for item in items:
            views = item.get("views", 0)
            total_views += views
        
        return total_views
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.debug(f"Page not found or no views: {page_title}")
            return 0
        logger.warning(f"HTTP error fetching pageviews for {page_title}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching pageviews for {page_title}: {e}")
        return None

def update_pageviews_for_all(update_existing: bool = False):
    """
    Update pageviews for all people in the database.
    
    Args:
        update_existing: If True, update all records. If False, only update records with no pageviews.
    """
    db = SessionLocal()
    
    try:
        # Get records (all or only those missing pageviews)
        if update_existing:
            all_people = db.query(FamousPerson).all()
            logger.info("Updating pageviews for ALL records (including existing)...")
        else:
            all_people = db.query(FamousPerson).filter(
                (FamousPerson.page_views.is_(None)) | (FamousPerson.page_views == 0)
            ).all()
            logger.info("Updating pageviews for records with missing or zero pageviews...")
        
        total = len(all_people)
        
        logger.info(f"Updating pageviews for {total} people...")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, person in enumerate(all_people, 1):
            # Extract page title from URL
            page_title = extract_page_title(person.wikipedia_url)
            
            if not page_title:
                logger.warning(f"[{idx}/{total}] Skipping {person.name}: Could not extract page title from URL")
                skipped_count += 1
                continue
            
            # Get pageviews
            logger.info(f"[{idx}/{total}] Fetching pageviews for {person.name} ({page_title})...")
            pageviews = get_pageviews_for_year(page_title)
            
            if pageviews is None:
                logger.warning(f"  Failed to get pageviews for {person.name}")
                error_count += 1
                continue
            
            # Update database
            person.page_views = pageviews
            updated_count += 1
            
            if pageviews > 0:
                logger.info(f"  ✓ Updated: {person.name} - {pageviews:,} views in past year")
            else:
                logger.info(f"  ✓ Updated: {person.name} - 0 views (page may not exist or have no data)")
            
            # Commit every 10 records to save progress
            if updated_count % 10 == 0:
                db.commit()
                logger.info(f"  Progress: {updated_count} updated, {skipped_count} skipped, {error_count} errors")
        
        # Final commit
        db.commit()
        
        logger.info("=" * 60)
        logger.info("UPDATE COMPLETE")
        logger.info(f"Total records: {total}")
        logger.info(f"Successfully updated: {updated_count}")
        logger.info(f"Skipped (no title): {skipped_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error updating pageviews: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Update Wikipedia pageviews for famous people")
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update all records, even if they already have pageviews"
    )
    args = parser.parse_args()
    
    update_pageviews_for_all(update_existing=args.update_all)

