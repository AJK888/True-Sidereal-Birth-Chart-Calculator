#!/usr/bin/env python3
"""Simple script to create example JSON files"""
import json
import requests
import sys
import time
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_BASE = "https://true-sidereal-api.onrender.com"

def create_session():
    """Create a requests session with retry logic and long timeouts"""
    session = requests.Session()
    
    # Retry strategy - NOTE: Do NOT retry on 429 (rate limit) errors
    # Retrying a 429 will just make it worse
    retry_strategy = Retry(
        total=2,  # Reduced retries
        backoff_factor=3,  # Longer backoff
        status_forcelist=[500, 502, 503, 504],  # Removed 429
        allowed_methods=["POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

def create_example(name, year, month, day, hour, minute, location):
    """Create an example JSON file"""
    print(f"Creating example for {name}...")
    session = create_session()
    
    # Calculate chart
    chart_payload = {
        "full_name": name,
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "location": location,
        "unknown_time": False,
        "no_full_name": False
    }
    
    print("  Calling calculate_chart API (this may take 1-2 minutes)...")
    try:
        # Increased timeout: (connect timeout, read timeout)
        chart_response = session.post(
            f"{API_BASE}/calculate_chart", 
            json=chart_payload, 
            timeout=(30, 300)  # 30s connect, 5min read
        )
        
        # Handle rate limiting
        if chart_response.status_code == 429:
            retry_after = chart_response.headers.get('Retry-After', '60')
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60
            print(f"  ⚠ Rate limited. Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            # Retry once after waiting
            chart_response = session.post(
                f"{API_BASE}/calculate_chart", 
                json=chart_payload, 
                timeout=(30, 300)
            )
        
        chart_response.raise_for_status()
        chart_data = chart_response.json()
        print("  ✓ Chart calculated")
    except requests.exceptions.Timeout:
        print("  ✗ Chart calculation timed out. The API may be slow. Try again later.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error calculating chart: {e}")
        if hasattr(e.response, 'status_code') and e.response.status_code == 429:
            print("  ⚠ Rate limit exceeded. Please wait a few minutes and try again.")
        raise
    
    # Generate reading
    reading_payload = {
        "chart_data": chart_data,
        "unknown_time": False,
        "user_inputs": {"full_name": name}
    }
    
    print("  Calling generate_reading API (this may take 2-3 minutes)...")
    # Add delay before reading request to avoid rate limits
    time.sleep(5)
    
    try:
        # Even longer timeout for AI reading generation
        reading_response = session.post(
            f"{API_BASE}/generate_reading", 
            json=reading_payload, 
            timeout=(30, 600)  # 30s connect, 10min read
        )
        
        # Handle rate limiting
        if reading_response.status_code == 429:
            retry_after = reading_response.headers.get('Retry-After', '60')
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60
            print(f"  ⚠ Rate limited. Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
            # Retry once after waiting
            reading_response = session.post(
                f"{API_BASE}/generate_reading", 
                json=reading_payload, 
                timeout=(30, 600)
            )
        
        reading_response.raise_for_status()
        reading_result = reading_response.json()
        ai_reading = reading_result.get("gemini_reading", "")
        print("  ✓ Reading generated")
    except requests.exceptions.Timeout:
        print("  ✗ Reading generation timed out. The API may be slow. Try again later.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error generating reading: {e}")
        if hasattr(e.response, 'status_code') and e.response.status_code == 429:
            print("  ⚠ Rate limit exceeded. Please wait a few minutes and try again.")
        raise
    
    # Format output
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    birth_date = f"{month_names[month-1]} {day}, {year}"
    
    if hour == 0:
        display_hour, period = 12, "AM"
    elif hour < 12:
        display_hour, period = hour, "AM"
    elif hour == 12:
        display_hour, period = 12, "PM"
    else:
        display_hour, period = hour - 12, "PM"
    birth_time = f"{display_hour}:{minute:02d} {period}"
    
    output = {
        "metadata": {
            "name": name,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "location": location,
            "unknown_time": False
        },
        "ai_reading": ai_reading,
        "chart_data": chart_data
    }
    
    # Save to correct location
    script_dir = Path(__file__).parent
    frontend_dir = script_dir / "True-Sidereal-Birth-Chart-Calculator"
    if not frontend_dir.exists():
        frontend_dir = script_dir
    output_dir = frontend_dir / "examples" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    output_path = output_dir / f"{filename}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved to: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    try:
        # Elon Musk
        print("=" * 60)
        print("Generating Elon Musk example...")
        print("=" * 60)
        create_example("Elon Musk", 1971, 6, 28, 7, 30, "Pretoria, South Africa")
        print()
        print("Waiting 30 seconds before next request to avoid rate limits...")
        time.sleep(30)  # Longer pause between examples to avoid rate limits
        
        # Barack Obama
        print("=" * 60)
        print("Generating Barack Obama example...")
        print("=" * 60)
        create_example("Barack Obama", 1961, 8, 4, 19, 24, "Honolulu, Hawaii, USA")
        print()
        
        print("=" * 60)
        print("All examples created successfully!")
        print("=" * 60)
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

