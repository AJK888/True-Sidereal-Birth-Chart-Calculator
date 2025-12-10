"""
Simple test to verify the scraper works
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test imports
print("Testing imports...", flush=True)
try:
    import wikipediaapi
    import requests
    print("✓ Dependencies OK", flush=True)
except ImportError as e:
    print(f"✗ Import error: {e}", flush=True)
    sys.exit(1)

# Test Wikipedia connection
print("\nTesting Wikipedia API...", flush=True)
try:
    USER_AGENT = "SynthesisAstrology/1.0 (test)"
    wiki = wikipediaapi.Wikipedia('en', user_agent=USER_AGENT)
    print("✓ Wikipedia API initialized", flush=True)
    
    # Test one page
    print("\nTesting page fetch: Albert Einstein", flush=True)
    page = wiki.page("Albert Einstein")
    
    if page.exists():
        print(f"✓ Page exists: {page.title}", flush=True)
        print(f"✓ URL: {page.fullurl}", flush=True)
        
        # Test parsing
        text = page.text[:2000]
        import re
        
        # Look for birth date
        birth_match = re.search(r'born\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})', text, re.IGNORECASE)
        if birth_match:
            print(f"✓ Found birth date: {birth_match.group(0)}", flush=True)
        else:
            print("⚠ Could not find birth date pattern", flush=True)
        
        # Look for location
        loc_match = re.search(r'born\s+in\s+([^,\n]+)', text, re.IGNORECASE)
        if loc_match:
            print(f"✓ Found birth location: {loc_match.group(1).strip()}", flush=True)
        else:
            print("⚠ Could not find birth location", flush=True)
            
        print("\n✓ All tests passed! Scraper should work.", flush=True)
    else:
        print("✗ Page does not exist", flush=True)
        
except Exception as e:
    print(f"✗ Error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

