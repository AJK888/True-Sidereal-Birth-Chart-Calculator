#!/usr/bin/env python3
"""Generate complete examples (chart + reading) for both Elon and Obama"""
import json
import requests
import sys
import time
from pathlib import Path
from datetime import datetime

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = "my-super-secret-key-12345"

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open("both_examples.log", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_complete_example(name, year, month, day, hour, minute, location):
    """Create a complete example with chart data and AI reading"""
    log("="*60)
    log(f"Generating complete example for {name}")
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
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        chart_response = requests.post(
            f"{API_BASE}/calculate_chart",
            json=chart_payload,
            headers=headers,
            timeout=(30, 180)
        )
        
        if chart_response.status_code != 200:
            log(f"  ✗ Error: {chart_response.text[:500]}")
            return False
        
        chart_data = chart_response.json()
        log("  ✓ Chart calculated successfully")
        
    except Exception as e:
        log(f"  ✗ Error: {type(e).__name__}: {e}")
        return False
    
    # Step 2: Generate reading
    log("Step 2: Generating AI reading (10-15 minutes)...")
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
            timeout=(30, 900)  # 15 minutes
        )
        
        if reading_response.status_code != 200:
            log(f"  ✗ Error: {reading_response.text[:500]}")
            return False
        
        reading_result = reading_response.json()
        ai_reading = reading_result.get("gemini_reading", "")
        
        if not ai_reading:
            log("  ⚠ Warning: Empty reading received")
            return False
        
        log(f"  ✓ Reading generated ({len(ai_reading)} characters)")
        
    except requests.exceptions.Timeout:
        log("  ✗ Request timed out after 15 minutes")
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
    log(f"✓ {name} example completed!")
    log("="*60)
    return True

if __name__ == "__main__":
    # Clear old log
    if Path("both_examples.log").exists():
        Path("both_examples.log").unlink()
    
    log("Starting generation of both examples...")
    log("This will take approximately 20-30 minutes total")
    log("")
    
    try:
        # Elon Musk
        success1 = create_complete_example("Elon Musk", 1971, 6, 28, 7, 30, "Pretoria, South Africa")
        
        if not success1:
            log("\n❌ Failed to generate Elon Musk example")
            sys.exit(1)
        
        log("\n⏳ Waiting 60 seconds before next request...")
        time.sleep(60)
        
        # Barack Obama
        success2 = create_complete_example("Barack Obama", 1961, 8, 4, 19, 24, "Honolulu, Hawaii, USA")
        
        if not success2:
            log("\n❌ Failed to generate Barack Obama example")
            sys.exit(1)
        
        log("\n" + "="*60)
        log("✓ Both examples generated successfully!")
        log("="*60)
        log("\nFiles saved to: True-Sidereal-Birth-Chart-Calculator/examples/data/")
        log("  - elon-musk.json (complete)")
        log("  - barack-obama.json (complete)")
        
    except KeyboardInterrupt:
        log("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        log(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

