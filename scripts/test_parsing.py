"""Quick test to see what's happening with the parsing."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scrape_and_calculate_5000 import get_infobox_data, parse_birth_date, parse_birth_location
import json

# Test with known people
test_cases = [
    "Bruce_Lee",
    "Albert_Einstein", 
    "Barack_Obama",
    "Taylor_Swift"
]

print("=" * 70)
print("TESTING PARSING FUNCTIONS")
print("=" * 70)

for name in test_cases:
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    
    result = get_infobox_data(name)
    
    if not result:
        print(f"  ❌ No data returned")
        continue
    
    print(f"  Title: {result.get('title', 'N/A')}")
    print(f"  URL: {result.get('url', 'N/A')}")
    
    birth_date = result.get('birth_date')
    if birth_date:
        print(f"  ✅ Birth Date: {birth_date.get('year')}-{birth_date.get('month')}-{birth_date.get('day')}")
    else:
        print(f"  ❌ No birth date")
    
    birth_location = result.get('birth_location')
    if birth_location:
        print(f"  ✅ Birth Location: {birth_location}")
    else:
        print(f"  ❌ No birth location")
    
    # Check if it would pass the filter
    if result and result.get('birth_date') and result.get('birth_location'):
        birth_date = result.get('birth_date', {})
        if birth_date.get('year') and birth_date.get('month') and birth_date.get('day'):
            print(f"  ✅✅ WOULD BE ADDED TO LIST")
        else:
            print(f"  ⚠️  Has date/location but missing year/month/day")
    else:
        print(f"  ❌ Would NOT be added (missing date or location)")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

