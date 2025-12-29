"""
Generate a test reading to verify prompt improvements.

This script generates a reading using the Sofie AlQattan chart data
to verify all the improvements are working correctly.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variable for stub mode if no API key
if not os.getenv("GEMINI_API_KEY"):
    print("WARNING: No GEMINI_API_KEY found. Setting AI_MODE=stub for testing.")
    os.environ["AI_MODE"] = "stub"

from app.services.llm_prompts import get_gemini3_reading

# Test chart data - Sofie AlQattan (from the graded reading)
# This chart has a 12th house stellium, planets in dignities, and tight aspects
test_chart_data = {
    "name": "Sofie AlQattan",
    "utc_datetime": "2005-04-25 06:00:00",
    "location": "Kuwait City, Kuwait",
    "unknown_time": False,
    # This is a simplified version - in reality, the chart calculation
    # would generate all the detailed positions
    "sidereal_major_positions": [
        {"name": "Sun", "position": "3°34' Aries", "house": 12},
        {"name": "Moon", "position": "1°10' Libra", "house": 6},
        {"name": "Venus", "position": "10°00' Aries", "house": 12},
        {"name": "Mars", "position": "24°56' Capricorn", "house": 10},
        {"name": "Jupiter", "position": "18°17' Virgo (Rx)", "house": 5},
        {"name": "Saturn", "position": "23°24' Gemini", "house": 3},
        {"name": "Uranus", "position": "13°27' Aquarius", "house": 10},
        {"name": "Neptune", "position": "16°43' Capricorn", "house": 9},
        {"name": "Pluto", "position": "9°25' Ophiuchus (Rx)", "house": 8},
        {"name": "True Node", "position": "33°20' Pisces (Rx)", "house": 12},
    ],
    "tropical_major_positions": [
        {"name": "Sun", "position": "5°01' Taurus", "house": 12},
        {"name": "Moon", "position": "13°56' Scorpio", "house": 6},
        {"name": "Venus", "position": "11°27' Taurus", "house": 12},
        {"name": "Mars", "position": "25°39' Aquarius", "house": 10},
        {"name": "Jupiter", "position": "11°21' Libra (Rx)", "house": 5},
        {"name": "Saturn", "position": "21°26' Cancer", "house": 3},
        {"name": "Uranus", "position": "9°45' Pisces", "house": 10},
        {"name": "Neptune", "position": "17°26' Aquarius", "house": 9},
        {"name": "Pluto", "position": "24°18' Sagittarius (Rx)", "house": 8},
        {"name": "True Node", "position": "22°48' Aries (Rx)", "house": 12},
    ],
    "sidereal_aspects": [
        {"aspect": "Venus Quincunx Jupiter", "orb": 0.10},
        {"aspect": "Moon Biquintile Mercury", "orb": 0.09},
        {"aspect": "Pluto Trine True Node", "orb": 1.50},
        {"aspect": "Saturn Square True Node", "orb": 1.37},
        {"aspect": "Moon Opposition Venus", "orb": 2.48},
        {"aspect": "Mars Sextile Pluto", "orb": 1.35},
        {"aspect": "Mars Sesquiquadrate Jupiter", "orb": 0.70},
    ],
    "tropical_aspects": [
        {"aspect": "Venus Quincunx Jupiter", "orb": 0.10},
        {"aspect": "Moon Biquintile Mercury", "orb": 0.09},
        {"aspect": "Pluto Trine True Node", "orb": 1.50},
        {"aspect": "Saturn Square True Node", "orb": 1.37},
        {"aspect": "Moon Opposition Venus", "orb": 2.48},
        {"aspect": "Mars Sextile Pluto", "orb": 1.35},
        {"aspect": "Mars Sesquiquadrate Jupiter", "orb": 0.70},
    ],
    "numerology_analysis": {
        "life_path_number": 9,
        "day_number": 7
    },
    "chinese_zodiac": "Rooster"
}


async def main():
    """Generate a test reading."""
    print("=" * 80)
    print("GENERATING TEST READING")
    print("=" * 80)
    print()
    print("Chart: Sofie AlQattan")
    print("Birth: 2005-04-25 06:00:00")
    print("Location: Kuwait City, Kuwait")
    print()
    print("This chart has:")
    print("- 12th House Stellium (Sun, Venus, True Node)")
    print("- Mars in Capricorn (Exalted)")
    print("- Moon in Scorpio (Fall)")
    print("- Multiple tight aspects (5+ with orbs < 2°)")
    print()
    print("Generating reading...")
    print("-" * 80)
    print()
    
    try:
        # Generate reading (without database for testing)
        reading = await get_gemini3_reading(
            chart_data=test_chart_data,
            unknown_time=False,
            db=None  # No database for testing
        )
        
        print("=" * 80)
        print("READING GENERATED SUCCESSFULLY")
        print("=" * 80)
        print()
        print(f"Reading length: {len(reading):,} characters")
        print()
        
        # Save to file
        output_file = project_root / "test_reading_output.txt"
        output_file.write_text(reading, encoding='utf-8')
        print(f"Reading saved to: {output_file}")
        print()
        
        # Quick verification checks
        print("VERIFICATION CHECKS:")
        print("-" * 80)
        
        checks = {
            "Stellium explicitly listed": [
                "12th House Stellium includes",
                "Stellium includes",
                "Sun in Aries" in reading and "Venus in Aries" in reading and "True Node" in reading,
            ],
            "Planetary Dignities section": [
                "Planetary Dignities",
                "Exaltation" in reading or "exalted" in reading.lower(),
                "Fall" in reading or "fall" in reading.lower(),
            ],
            "5+ Aspects covered": reading.count("aspect") >= 5 or reading.count("Aspect") >= 5,
            "Houses section": "Houses & Life Domains" in reading or "HOUSES" in reading,
            "Spiritual Path separate": "Spiritual Path & Meaning" in reading,
            "Famous People separate": "Famous People" in reading,
            "How Shadows Interact": "How Shadows Interact" in reading or "how shadows interact" in reading.lower(),
            "Concrete examples": reading.count("When") > 10 or reading.count("In ") > 20,
        }
        
        for check_name, conditions in checks.items():
            if isinstance(conditions, list):
                passed = any(condition if isinstance(condition, bool) else condition in reading for condition in conditions)
            else:
                passed = conditions
            
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status} {check_name}")
        
        print()
        print("=" * 80)
        print("Full reading is in: test_reading_output.txt")
        print("Review it to verify all requirements are met.")
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

