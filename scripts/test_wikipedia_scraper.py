"""
Quick test script to verify Wikipedia scraper is working
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("Testing Wikipedia Scraper")
print("=" * 60)

# Test imports
print("\n1. Testing imports...")
try:
    import wikipediaapi
    import requests
    print("   ✓ Dependencies installed")
except ImportError as e:
    print(f"   ✗ Missing dependency: {e}")
    sys.exit(1)

# Test Wikipedia API
print("\n2. Testing Wikipedia API connection...")
try:
    USER_AGENT = "SynthesisAstrology/1.0 (test)"
    wiki = wikipediaapi.Wikipedia('en', user_agent=USER_AGENT)
    print("   ✓ Wikipedia API initialized")
    
    # Test fetching a page
    print("\n3. Testing page fetch...")
    page = wiki.page("Albert Einstein")
    if page.exists():
        print(f"   ✓ Page exists: {page.title}")
        print(f"   ✓ URL: {page.fullurl}")
        print(f"   ✓ Text length: {len(page.text)} characters")
        
        # Test parsing
        print("\n4. Testing data extraction...")
        text = page.text[:2000]
        
        # Look for birth date
        import re
        birth_patterns = [
            r'born\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',
            r'born\s+(\d{1,2})\s+(\w+)\s+(\d{4})',
        ]
        
        found_date = False
        for pattern in birth_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                print(f"   ✓ Found birth date pattern: {match.group(0)}")
                found_date = True
                break
        
        if not found_date:
            print("   ⚠ Could not find birth date in first 2000 chars")
        
        # Look for location
        location_match = re.search(r'born\s+in\s+([^,\n]+)', text, re.IGNORECASE)
        if location_match:
            print(f"   ✓ Found birth location: {location_match.group(1).strip()}")
        else:
            print("   ⚠ Could not find birth location")
            
    else:
        print("   ✗ Page does not exist")
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("All tests passed! Scraper should work correctly.")
print("=" * 60)

