#!/usr/bin/env python3
"""Update Obama's chart data only (keep existing reading)"""
import json
import requests

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = "my-super-secret-key-12345"

print("Calculating chart for Barack Obama...")

chart_payload = {
    "full_name": "Barack Obama",
    "year": 1961,
    "month": 8,
    "day": 4,
    "hour": 19,
    "minute": 24,
    "location": "Honolulu, Hawaii, USA",
    "unknown_time": False,
    "no_full_name": False
}

try:
    headers = {"x-admin-secret": ADMIN_SECRET}
    chart_response = requests.post(
        f"{API_BASE}/calculate_chart",
        json=chart_payload,
        headers=headers,
        timeout=(30, 180)
    )
    
    if chart_response.status_code != 200:
        print(f"Error: {chart_response.text[:500]}")
        exit(1)
    
    chart_data = chart_response.json()
    print("✓ Chart calculated successfully")
    
    # Read existing file
    with open('True-Sidereal-Birth-Chart-Calculator/examples/data/barack-obama.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Update only chart_data, keep metadata and ai_reading
    data['chart_data'] = chart_data
    
    # Write back
    with open('True-Sidereal-Birth-Chart-Calculator/examples/data/barack-obama.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print("✓ Updated barack-obama.json with chart data")
    
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

