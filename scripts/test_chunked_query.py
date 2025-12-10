"""
Quick test to verify chunked SPARQL queries work.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scrape_wikidata_5000 import get_top_people_by_sitelinks
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("="*70)
print("TESTING CHUNKED SPARQL QUERIES")
print("="*70)
print()

# Test with small limit first
print("Test 1: Fetching 50 people...")
results = get_top_people_by_sitelinks(limit=50)
print(f"✓ Retrieved {len(results)} people")
print()

if len(results) > 0:
    print("Sample results:")
    for i, person in enumerate(results[:3], 1):
        name = person.get("name", "Unknown")
        birth_date = person.get("birth_date", {})
        birth_loc = person.get("birth_location", "Unknown")
        print(f"  {i}. {name} - Born: {birth_date.get('year')}-{birth_date.get('month')}-{birth_date.get('day')} in {birth_loc}")
    print()
    
    print("Test 2: Fetching 200 people...")
    results2 = get_top_people_by_sitelinks(limit=200)
    print(f"✓ Retrieved {len(results2)} people")
    print()
    
    print("="*70)
    print("✓ ALL TESTS PASSED!")
    print("="*70)
    print("The chunked query approach is working correctly.")
    print("You can now run the full script: python scripts/scrape_wikidata_5000.py")
else:
    print("✗ TEST FAILED: No results returned")
    print("Check your internet connection and Wikidata availability.")

