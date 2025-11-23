#!/usr/bin/env python3
"""Generate Elon example with chart data only (no AI reading) - faster"""
import json
import requests
import sys
from pathlib import Path
from datetime import datetime

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = "my-super-secret-key-12345"

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open("elon_generation.log", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def create_example_chart_only():
    """Generate example with chart data only (no AI reading)"""
    name = "Elon Musk"
    year, month, day = 1971, 6, 28
    hour, minute = 7, 30
    location = "Pretoria, South Africa"
    
    log("="*60)
    log(f"Generating chart for {name} (without AI reading)")
    log("="*60)
    
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
    
    log("Calculating chart...")
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        chart_response = requests.post(
            f"{API_BASE}/calculate_chart",
            json=chart_payload,
            headers=headers,
            timeout=(30, 180)
        )
        
        log(f"Status: {chart_response.status_code}")
        
        if chart_response.status_code != 200:
            error_text = chart_response.text[:500]
            log(f"✗ Error: {error_text}")
            return False
        
        chart_data = chart_response.json()
        log("✓ Chart calculated successfully")
        
    except Exception as e:
        log(f"✗ Error: {type(e).__name__}: {e}")
        return False
    
    # Save with placeholder reading
    log("Saving file with chart data (AI reading will be added later)...")
    
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
        "ai_reading": "AI reading generation in progress... (This will be updated)",
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
    
    log(f"✓ Saved to: {output_path}")
    log("="*60)
    log("✓ Chart data saved! You can add the AI reading later.")
    log("="*60)
    return True

if __name__ == "__main__":
    if Path("elon_generation.log").exists():
        Path("elon_generation.log").unlink()
    
    try:
        success = create_example_chart_only()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        log(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

