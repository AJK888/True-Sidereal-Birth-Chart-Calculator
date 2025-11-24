#!/usr/bin/env python3
"""Generate Elon example with logging to file"""
import json
import os
import requests
import sys
import time
from pathlib import Path
from datetime import datetime

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET:
    print("Error: ADMIN_SECRET_KEY environment variable not set")
    sys.exit(1)

def log(msg):
    """Log to both console and file"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open("elon_generation.log", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_example():
    name = "Elon Musk"
    year, month, day = 1971, 6, 28
    hour, minute = 7, 30
    location = "Pretoria, South Africa"
    
    log("="*60)
    log(f"Generating example for {name}")
    log("="*60)
    
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
    
    log("Step 1: Calculating chart...")
    log(f"  API: {API_BASE}/calculate_chart")
    
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        log("  Sending request (timeout: 3 minutes)...")
        
        chart_response = requests.post(
            f"{API_BASE}/calculate_chart",
            json=chart_payload,
            headers=headers,
            timeout=(30, 180)
        )
        
        log(f"  Status: {chart_response.status_code}")
        
        if chart_response.status_code != 200:
            error_text = chart_response.text[:500]
            log(f"  ✗ Error: {error_text}")
            return False
        
        chart_data = chart_response.json()
        log("  ✓ Chart calculated successfully")
        
    except requests.exceptions.Timeout:
        log("  ✗ Request timed out after 3 minutes")
        log("  The API may be sleeping or very slow")
        return False
    except Exception as e:
        log(f"  ✗ Error: {type(e).__name__}: {e}")
        return False
    
    # Step 2: Generate reading
    log("Step 2: Generating AI reading...")
    log(f"  API: {API_BASE}/generate_reading")
    
    reading_payload = {
        "chart_data": chart_data,
        "unknown_time": False,
        "user_inputs": {"full_name": name}
    }
    
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        log("  Sending request (timeout: 15 minutes - multiple Gemini calls)...")
        
        reading_response = requests.post(
            f"{API_BASE}/generate_reading",
            json=reading_payload,
            headers=headers,
            timeout=(30, 900)  # 30s connect, 15min read (increased for multiple Gemini calls)
        )
        
        log(f"  Status: {reading_response.status_code}")
        
        if reading_response.status_code != 200:
            error_text = reading_response.text[:500]
            log(f"  ✗ Error: {error_text}")
            return False
        
        reading_result = reading_response.json()
        ai_reading = reading_result.get("gemini_reading", "")
        
        if not ai_reading:
            log("  ⚠ Warning: Empty reading received")
        else:
            log(f"  ✓ Reading generated ({len(ai_reading)} characters)")
        
    except requests.exceptions.Timeout:
        log("  ✗ Request timed out after 15 minutes")
        log("  The Gemini API is making multiple sequential calls which can take 10-15 minutes")
        return False
    except Exception as e:
        log(f"  ✗ Error: {type(e).__name__}: {e}")
        return False
    
    # Step 3: Save file
    log("Step 3: Saving file...")
    
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
    
    log(f"  ✓ Saved to: {output_path}")
    log("="*60)
    log("✓ Example generated successfully!")
    log("="*60)
    return True

if __name__ == "__main__":
    # Clear old log
    if Path("elon_generation.log").exists():
        Path("elon_generation.log").unlink()
    
    try:
        success = create_example()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        log(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

