#!/usr/bin/env python3
"""Simplified script with better error handling and progress"""
import json
import os
import requests
import sys
import time
from pathlib import Path

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET:
    print("Error: ADMIN_SECRET_KEY environment variable not set")
    sys.exit(1)

def create_example():
    name = "Elon Musk"
    year, month, day = 1971, 6, 28
    hour, minute = 7, 30
    location = "Pretoria, South Africa"
    
    print("="*60)
    print(f"Generating example for {name}")
    print("="*60)
    print()
    
    # Step 1: Calculate chart
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
    
    print("Step 1: Calculating chart...")
    print(f"  API: {API_BASE}/calculate_chart")
    print("  This may take 1-2 minutes (API may be waking up)...")
    
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        chart_response = requests.post(
            f"{API_BASE}/calculate_chart",
            json=chart_payload,
            headers=headers,
            timeout=(30, 180)
        )
        
        print(f"  Status: {chart_response.status_code}")
        
        if chart_response.status_code != 200:
            print(f"  ✗ Error: {chart_response.text[:500]}")
            return False
        
        chart_data = chart_response.json()
        print("  ✓ Chart calculated successfully")
        print()
        
    except requests.exceptions.Timeout:
        print("  ✗ Request timed out")
        print("  The API may be sleeping. Try again in a moment.")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False
    
    # Step 2: Generate reading
    print("Step 2: Generating AI reading...")
    print(f"  API: {API_BASE}/generate_reading")
    print("  This may take 2-3 minutes...")
    
    reading_payload = {
        "chart_data": chart_data,
        "unknown_time": False,
        "user_inputs": {"full_name": name}
    }
    
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        reading_response = requests.post(
            f"{API_BASE}/generate_reading",
            json=reading_payload,
            headers=headers,
            timeout=(30, 300)
        )
        
        print(f"  Status: {reading_response.status_code}")
        
        if reading_response.status_code != 200:
            print(f"  ✗ Error: {reading_response.text[:500]}")
            return False
        
        reading_result = reading_response.json()
        ai_reading = reading_result.get("gemini_reading", "")
        
        if not ai_reading:
            print("  ⚠ Warning: Empty reading received")
        
        print(f"  ✓ Reading generated ({len(ai_reading)} characters)")
        print()
        
    except requests.exceptions.Timeout:
        print("  ✗ Request timed out")
        print("  The AI reading generation is taking too long.")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False
    
    # Step 3: Save file
    print("Step 3: Saving file...")
    
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
    print()
    print("="*60)
    print("✓ Example generated successfully!")
    print("="*60)
    return True

if __name__ == "__main__":
    try:
        success = create_example()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

