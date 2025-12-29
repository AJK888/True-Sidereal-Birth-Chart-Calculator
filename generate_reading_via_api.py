"""
Generate a reading via the API endpoint and grade it.

This script calls the deployed API to generate a reading.
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
API_BASE = "https://true-sidereal-api.onrender.com"
TEST_EMAIL = "test@synthesisastrology.com"

# Test chart data
chart_request = {
    "full_name": "Sofie AlQattan",
    "year": 2005,
    "month": 4,
    "day": 25,
    "hour": 6,
    "minute": 0,
    "location": "Kuwait City, Kuwait",
    "unknown_time": False,
    "is_full_birth_name": False
}

reading_request = {
    "chart_data": {},  # Will be filled after chart calculation
    "user_inputs": {
        "full_name": "Sofie AlQattan",
        "user_email": TEST_EMAIL
    }
}


def grade_reading(reading: str) -> dict:
    """Grade the reading against requirements."""
    reading_lower = reading.lower()
    
    checks = {
        "Stellium explicit listing": any([
            "stellium includes" in reading_lower,
            "stellium contains" in reading_lower,
            ("sun in aries" in reading_lower and "venus in aries" in reading_lower and "true node" in reading_lower)
        ]),
        "Planetary Dignities section": (
            "planetary dignities" in reading_lower or 
            "dignities & conditions" in reading_lower
        ),
        "5+ Aspects covered": reading.count("aspect") + reading.count("Aspect") >= 5,
        "Aspect mechanisms explained": sum(1 for kw in ["why", "because", "mechanism", "creates"] if kw in reading_lower) >= 3,
        "All 12 houses": sum(1 for i in range(1, 13) if f"{i}st house" in reading_lower or f"{i}nd house" in reading_lower or 
                            f"{i}rd house" in reading_lower or f"{i}th house" in reading_lower or f"house {i}" in reading_lower) >= 12,
        "Spiritual Path separate": "spiritual path" in reading_lower,
        "Famous People separate": "famous people" in reading_lower,
        "Concrete examples": sum(1 for kw in ["when", "in relationships", "at work", "this shows up"] if kw in reading_lower) >= 15,
        "How Shadows Interact": "how shadows interact" in reading_lower,
        "Emotional Life depth": any(kw in reading_lower for kw in ["family dynamics", "childhood patterns", "healing modalities"]),
        "Work/Money depth": any(kw in reading_lower for kw in ["career paths", "money patterns"]),
        "Operating System expanded": "operating system" in reading_lower and ("default mode" in reading_lower or "high expression" in reading_lower),
    }
    
    pass_count = sum(1 for v in checks.values() if v)
    total = len(checks)
    score = (pass_count / total) * 100
    
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "grade": grade,
        "score": score,
        "checks": checks,
        "pass_count": pass_count,
        "total": total
    }


def main():
    """Generate reading via API and grade it."""
    print("=" * 80)
    print("GENERATING READING VIA API")
    print("=" * 80)
    print()
    
    # Step 1: Calculate chart
    print("Step 1: Calculating chart...")
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/charts/calculate_chart",
            json=chart_request,
            timeout=30
        )
        response.raise_for_status()
        chart_data = response.json()
        print("✓ Chart calculated")
        print()
    except Exception as e:
        print(f"ERROR: Failed to calculate chart: {e}")
        return 1
    
    # Step 2: Generate reading
    print("Step 2: Generating reading...")
    print("(This may take 5-10 minutes)")
    print("-" * 80)
    
    reading_request["chart_data"] = chart_data
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/charts/generate_reading",
            json=reading_request,
            timeout=600  # 10 minute timeout
        )
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "processing":
            print("✓ Reading queued for generation")
            print("Reading will be sent to email when complete.")
            print()
            print("Note: For immediate testing, you may need to:")
            print("1. Check the email for the reading")
            print("2. Or wait for the background task to complete")
            print("3. Or retrieve it via /get_reading/{chart_hash}")
            return 0
        else:
            print(f"Unexpected response: {result}")
            return 1
            
    except Exception as e:
        print(f"ERROR: Failed to generate reading: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

