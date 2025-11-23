#!/usr/bin/env python3
"""Create a single example JSON file - use this to avoid rate limits"""
import json
import requests
import sys
import time
from pathlib import Path

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = "my-super-secret-key-12345"  # Admin secret to bypass rate limits

def create_example(name, year, month, day, hour, minute, location):
    """Create an example JSON file"""
    print(f"Creating example for {name}...")
    
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
    print(f"  API URL: {API_BASE}/calculate_chart")
    print(f"  Using admin secret to bypass rate limits")
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        print("  Sending request...")
        chart_response = requests.post(
            f"{API_BASE}/calculate_chart", 
            json=chart_payload,
            headers=headers,
            timeout=(30, 180)  # 30s connect, 3min read (reduced from 5min)
        )
        print(f"  Response status: {chart_response.status_code}")
        
        # Handle rate limiting
        if chart_response.status_code == 429:
            retry_after = chart_response.headers.get('Retry-After', '60')
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60
            print(f"  ⚠ Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            chart_response = requests.post(
                f"{API_BASE}/calculate_chart", 
                json=chart_payload,
                headers=headers,
                timeout=(30, 300)
            )
        
        chart_response.raise_for_status()
        chart_data = chart_response.json()
        print("  ✓ Chart calculated")
    except requests.exceptions.Timeout:
        print("  ✗ Chart calculation timed out.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error: {e}")
        if hasattr(e, 'response') and e.response and e.response.status_code == 429:
            print("  ⚠ Rate limit exceeded. Please wait 5-10 minutes and try again.")
        raise
    
    # Wait before reading request
    print("  Waiting 10 seconds before reading request...")
    time.sleep(10)
    
    # Generate reading
    reading_payload = {
        "chart_data": chart_data,
        "unknown_time": False,
        "user_inputs": {"full_name": name}
    }
    
    print("  Calling generate_reading API (this may take 2-3 minutes)...")
    print(f"  API URL: {API_BASE}/generate_reading")
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        print("  Sending request...")
        reading_response = requests.post(
            f"{API_BASE}/generate_reading", 
            json=reading_payload,
            headers=headers,
            timeout=(30, 300)  # 30s connect, 5min read (reduced from 10min)
        )
        print(f"  Response status: {reading_response.status_code}")
        
        # Handle rate limiting
        if reading_response.status_code == 429:
            retry_after = reading_response.headers.get('Retry-After', '60')
            try:
                wait_time = int(retry_after)
            except ValueError:
                wait_time = 60
            print(f"  ⚠ Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            reading_response = requests.post(
                f"{API_BASE}/generate_reading", 
                json=reading_payload,
                headers=headers,
                timeout=(30, 600)
            )
        
        reading_response.raise_for_status()
        reading_result = reading_response.json()
        ai_reading = reading_result.get("gemini_reading", "")
        print("  ✓ Reading generated")
    except requests.exceptions.Timeout:
        print("  ✗ Reading generation timed out.")
        raise
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error: {e}")
        if hasattr(e, 'response') and e.response and e.response.status_code == 429:
            print("  ⚠ Rate limit exceeded. Please wait 5-10 minutes and try again.")
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Create a single example JSON file")
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--year", type=int, required=True, help="Birth year")
    parser.add_argument("--month", type=int, required=True, help="Birth month (1-12)")
    parser.add_argument("--day", type=int, required=True, help="Birth day")
    parser.add_argument("--hour", type=int, required=True, help="Birth hour (0-23)")
    parser.add_argument("--minute", type=int, default=0, help="Birth minute (0-59)")
    parser.add_argument("--location", required=True, help="Birth location")
    
    args = parser.parse_args()
    
    try:
        create_example(args.name, args.year, args.month, args.day, args.hour, args.minute, args.location)
        print("\n✓ Example created successfully!")
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}", file=sys.stderr)
        sys.exit(1)

