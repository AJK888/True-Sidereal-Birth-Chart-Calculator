"""
Quick test script to verify the new geocoding methods work correctly.
Tests Wikidata coordinates and Nominatim fallback.
"""
import os
import sys
import time
import requests
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

USER_AGENT = "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"
GEOCODING_CACHE = {}

def get_coordinates_from_wikidata(place_qid: str) -> Optional[Dict]:
    """Get coordinates directly from Wikidata using the place QID."""
    if not place_qid:
        return None
    
    cache_key = f"wikidata:{place_qid}"
    if cache_key in GEOCODING_CACHE:
        print(f"  [CACHE HIT] Wikidata: {place_qid}")
        return GEOCODING_CACHE[cache_key]
    
    try:
        print(f"  [FETCHING] Wikidata coordinates for {place_qid}...")
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": place_qid,
            "props": "claims",
            "format": "json"
        }
        
        time.sleep(0.2)
        response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        entities = data.get("entities", {})
        entity = entities.get(place_qid, {})
        claims = entity.get("claims", {})
        
        # P625 is the coordinate location property
        if "P625" in claims:
            coordinate_claim = claims["P625"][0]
            mainsnak = coordinate_claim.get("mainsnak", {})
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            
            latitude = value.get("latitude")
            longitude = value.get("longitude")
            
            if latitude and longitude:
                # Try to get timezone from the place (P421 is timezone property)
                timezone = "UTC"
                if "P421" in claims:
                    tz_claim = claims["P421"][0]
                    tz_mainsnak = tz_claim.get("mainsnak", {})
                    tz_datavalue = tz_mainsnak.get("datavalue", {})
                    tz_value = tz_datavalue.get("value", "")
                    if tz_value:
                        timezone = tz_value
                
                result = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone
                }
                GEOCODING_CACHE[cache_key] = result
                print(f"  [SUCCESS] Wikidata: {latitude}, {longitude}, timezone: {timezone}")
                return result
        else:
            print(f"  [FAILED] No coordinates found in Wikidata for {place_qid}")
    except Exception as e:
        print(f"  [ERROR] Wikidata geocoding failed: {e}")
    
    return None


def geocode_with_nominatim(location: str) -> Optional[Dict]:
    """Geocode using Nominatim (OpenStreetMap) - free and generous limits."""
    cache_key = f"nominatim:{location}"
    if cache_key in GEOCODING_CACHE:
        print(f"  [CACHE HIT] Nominatim: {location}")
        return GEOCODING_CACHE[cache_key]
    
    try:
        print(f"  [FETCHING] Nominatim coordinates for '{location}'...")
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": USER_AGENT
        }
        
        time.sleep(1.1)  # Nominatim requires max 1 request/second
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data and len(data) > 0:
            result_data = data[0]
            lat = float(result_data.get("lat", 0))
            lon = float(result_data.get("lon", 0))
            
            if lat and lon:
                result = {
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": "UTC"  # Nominatim doesn't provide timezone
                }
                GEOCODING_CACHE[cache_key] = result
                print(f"  [SUCCESS] Nominatim: {lat}, {lon}, timezone: UTC")
                return result
        else:
            print(f"  [FAILED] No results from Nominatim for '{location}'")
    except Exception as e:
        print(f"  [ERROR] Nominatim geocoding failed: {e}")
    
    return None


def test_geocoding():
    """Test the geocoding methods with various examples."""
    print("=" * 70)
    print("GEOCODING TEST - Verifying Wikidata and Nominatim Methods")
    print("=" * 70)
    print()
    
    # Test cases: (location_name, place_qid, description)
    test_cases = [
        ("New York City", "Q60", "Major city with Wikidata QID"),
        ("London", "Q84", "Major city with Wikidata QID"),
        ("Los Angeles", "Q65", "Major city with Wikidata QID"),
        ("Paris", "Q90", "Major city with Wikidata QID"),
        ("Tokyo", "Q1490", "Major city with Wikidata QID"),
        ("Berlin", None, "City without QID (will use Nominatim)"),
        ("San Francisco", None, "City without QID (will use Nominatim)"),
    ]
    
    success_count = 0
    fail_count = 0
    
    for location, place_qid, description in test_cases:
        print(f"\nTest: {location} ({description})")
        print("-" * 70)
        
        result = None
        
        # Try Wikidata first if QID provided
        if place_qid:
            result = get_coordinates_from_wikidata(place_qid)
        
        # Fall back to Nominatim if Wikidata failed or no QID
        if not result:
            result = geocode_with_nominatim(location)
        
        if result:
            print(f"✓ SUCCESS: {location}")
            print(f"  Coordinates: {result['latitude']}, {result['longitude']}")
            print(f"  Timezone: {result['timezone']}")
            success_count += 1
        else:
            print(f"✗ FAILED: {location}")
            fail_count += 1
        
        time.sleep(0.5)  # Small delay between tests
    
    # Test caching
    print("\n" + "=" * 70)
    print("TESTING CACHE (should be instant)")
    print("=" * 70)
    print("\nRe-querying New York City (should use cache)...")
    result = get_coordinates_from_wikidata("Q60")
    if result:
        print("✓ Cache working correctly!")
    
    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)
    print(f"Successful: {success_count}/{len(test_cases)}")
    print(f"Failed: {fail_count}/{len(test_cases)}")
    print(f"Cache size: {len(GEOCODING_CACHE)} entries")
    
    if success_count == len(test_cases):
        print("\n✓ ALL TESTS PASSED!")
    else:
        print(f"\n⚠ {fail_count} test(s) failed")
    
    print("=" * 70)


if __name__ == "__main__":
    test_geocoding()

