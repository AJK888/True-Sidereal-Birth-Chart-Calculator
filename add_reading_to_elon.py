#!/usr/bin/env python3
"""Add AI reading to existing elon-musk.json file"""
import json
import os
import requests
import sys
from pathlib import Path
from datetime import datetime

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET:
    print("Error: ADMIN_SECRET_KEY environment variable not set")
    sys.exit(1)

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open("elon_generation.log", "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def add_reading():
    log("="*60)
    log("Adding AI reading to elon-musk.json")
    log("="*60)
    
    # Load existing file
    script_dir = Path(__file__).parent
    frontend_dir = script_dir / "True-Sidereal-Birth-Chart-Calculator"
    if not frontend_dir.exists():
        frontend_dir = script_dir
    json_path = frontend_dir / "examples" / "data" / "elon-musk.json"
    
    if not json_path.exists():
        log(f"✗ File not found: {json_path}")
        return False
    
    log(f"Loading existing file: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chart_data = data.get("chart_data", {})
    if not chart_data:
        log("✗ No chart_data found in file")
        return False
    
    name = data.get("metadata", {}).get("name", "Elon Musk")
    unknown_time = data.get("metadata", {}).get("unknown_time", False)
    
    log("Generating AI reading (this may take 10-15 minutes)...")
    log("  API: https://true-sidereal-api.onrender.com/generate_reading")
    
    reading_payload = {
        "chart_data": chart_data,
        "unknown_time": unknown_time,
        "user_inputs": {"full_name": name}
    }
    
    try:
        headers = {"x-admin-secret": ADMIN_SECRET}
        log("  Sending request (timeout: 15 minutes)...")
        
        reading_response = requests.post(
            f"{API_BASE}/generate_reading",
            json=reading_payload,
            headers=headers,
            timeout=(30, 900)  # 15 minutes
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
            return False
        
        log(f"  ✓ Reading generated ({len(ai_reading)} characters)")
        
        # Update the file
        log("Updating file with AI reading...")
        data["ai_reading"] = ai_reading
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        log(f"✓ File updated: {json_path}")
        log("="*60)
        log("✓ AI reading added successfully!")
        log("="*60)
        return True
        
    except requests.exceptions.Timeout:
        log("  ✗ Request timed out after 15 minutes")
        return False
    except Exception as e:
        log(f"  ✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = add_reading()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        log(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

