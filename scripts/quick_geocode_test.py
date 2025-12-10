"""Quick geocoding test - writes results to file"""
import requests
import time

USER_AGENT = "SynthesisAstrology/1.0"

# Test 1: Wikidata coordinates
print("Test 1: Wikidata coordinates for New York City (Q60)")
try:
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "ids": "Q60",
        "props": "claims",
        "format": "json"
    }
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        entities = data.get("entities", {})
        entity = entities.get("Q60", {})
        claims = entity.get("claims", {})
        
        if "P625" in claims:
            coord_claim = claims["P625"][0]
            value = coord_claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            lat = value.get("latitude")
            lon = value.get("longitude")
            print(f"SUCCESS: {lat}, {lon}")
        else:
            print("FAILED: No P625 property found")
    else:
        print(f"FAILED: HTTP {response.status_code}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "="*50)

# Test 2: Nominatim
print("Test 2: Nominatim for 'New York City'")
time.sleep(1.1)
try:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": "New York City", "format": "json", "limit": 1}
    response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data and len(data) > 0:
            result = data[0]
            lat = result.get("lat")
            lon = result.get("lon")
            print(f"SUCCESS: {lat}, {lon}")
        else:
            print("FAILED: No results")
    else:
        print(f"FAILED: HTTP {response.status_code}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "="*50)
print("Tests complete!")

