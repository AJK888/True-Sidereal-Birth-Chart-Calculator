"""
Test script to verify SPARQL connection to Wikidata works.
"""
import requests
import time

USER_AGENT = "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"

def test_small_query():
    """Test with a very small query (10 people)."""
    query = """
    SELECT ?person ?personLabel ?birthDate ?birthPlace ?birthPlaceLabel
    WHERE {
        ?person wdt:P31 wd:Q5 .  # Instance of: Human
        ?person wdt:P569 ?birthDate .  # Has date of birth
        ?person wdt:P19 ?birthPlace .  # Has place of birth
        
        SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
    }
    LIMIT 10
    """
    
    url = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    print("Testing SPARQL connection with small query (10 people)...")
    print(f"Query URL: {url}")
    print(f"Query size: {len(query)} characters")
    print()
    
    try:
        response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            print(f"✓ SUCCESS! Retrieved {len(bindings)} people")
            
            # Show first 3 results
            for i, binding in enumerate(bindings[:3], 1):
                name = binding.get("personLabel", {}).get("value", "Unknown")
                birth_date = binding.get("birthDate", {}).get("value", "Unknown")
                birth_place = binding.get("birthPlaceLabel", {}).get("value", "Unknown")
                print(f"  {i}. {name} - Born: {birth_date} in {birth_place}")
            
            return True
        else:
            print(f"✗ ERROR: Status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ ERROR: Request timed out")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def test_medium_query():
    """Test with a medium query (100 people)."""
    query = """
    SELECT ?person ?personLabel ?birthDate ?birthPlace ?birthPlaceLabel
    WHERE {
        ?person wdt:P31 wd:Q5 .  # Instance of: Human
        ?person wdt:P569 ?birthDate .  # Has date of birth
        ?person wdt:P19 ?birthPlace .  # Has place of birth
        
        SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
    }
    LIMIT 100
    """
    
    url = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    print("\n" + "="*70)
    print("Testing SPARQL connection with medium query (100 people)...")
    print()
    
    try:
        start_time = time.time()
        response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=60)
        elapsed = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Time taken: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            print(f"✓ SUCCESS! Retrieved {len(bindings)} people")
            return True
        else:
            print(f"✗ ERROR: Status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ ERROR: Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def test_large_query():
    """Test with a large query (1000 people)."""
    query = """
    SELECT ?person ?personLabel ?birthDate ?birthPlace ?birthPlaceLabel
    WHERE {
        ?person wdt:P31 wd:Q5 .  # Instance of: Human
        ?person wdt:P569 ?birthDate .  # Has date of birth
        ?person wdt:P19 ?birthPlace .  # Has place of birth
        
        SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
    }
    LIMIT 1000
    """
    
    url = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json"
    }
    
    print("\n" + "="*70)
    print("Testing SPARQL connection with large query (1000 people)...")
    print()
    
    try:
        start_time = time.time()
        response = requests.get(url, params={"query": query, "format": "json"}, headers=headers, timeout=120)
        elapsed = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Time taken: {elapsed:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            bindings = data.get("results", {}).get("bindings", [])
            print(f"✓ SUCCESS! Retrieved {len(bindings)} people")
            return True
        else:
            print(f"✗ ERROR: Status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ ERROR: Request timed out after 120 seconds")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("="*70)
    print("WIKIDATA SPARQL CONNECTION TEST")
    print("="*70)
    print()
    
    # Test small query
    small_works = test_small_query()
    
    if small_works:
        # Test medium query
        medium_works = test_medium_query()
        
        if medium_works:
            # Test large query
            large_works = test_large_query()
            
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Small query (10):   {'✓ PASS' if small_works else '✗ FAIL'}")
            print(f"Medium query (100): {'✓ PASS' if medium_works else '✗ FAIL'}")
            print(f"Large query (1000): {'✓ PASS' if large_works else '✗ FAIL'}")
            print()
            
            if large_works:
                print("Recommendation: Use chunks of 1000 people per query")
            elif medium_works:
                print("Recommendation: Use chunks of 100 people per query")
            else:
                print("Recommendation: Use chunks of 10-50 people per query")
        else:
            print("\nRecommendation: Use chunks of 10-50 people per query")
    else:
        print("\n✗ Basic connection failed. Check internet connection.")

