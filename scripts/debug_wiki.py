#!/usr/bin/env python3
"""Debug script to see what Wikipedia returns."""

import requests
import re

api_url = "https://en.wikipedia.org/w/api.php"
params = {
    "action": "query",
    "prop": "revisions",
    "rvprop": "content",
    "rvslots": "main",
    "titles": "Albert Einstein",
    "format": "json",
    "formatversion": "2"
}
headers = {"User-Agent": "Test/1.0"}

print("Fetching Albert Einstein page...")
response = requests.get(api_url, params=params, headers=headers, timeout=10)
data = response.json()

pages = data.get("query", {}).get("pages", [])
if pages and "revisions" in pages[0]:
    text = pages[0]["revisions"][0]["slots"]["main"]["content"]
    print(f"Got {len(text)} characters of wiki markup")
    
    # Find infobox
    start = text.find('{{Infobox')
    print(f"Infobox found at position: {start}")
    
    if start != -1:
        infobox_text = text[start:start+2000]
        print("\n" + "="*60)
        print("INFOBOX TEXT (first 2000 chars):")
        print("="*60)
        print(infobox_text)
        
        # Test patterns
        print("\n" + "="*60)
        print("TESTING PATTERNS:")
        print("="*60)
        
        # Pattern 1: {{birth date|1879|3|14}}
        pattern1 = r'\{\{birth date(?:\s+and\s+age)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match1 = re.search(pattern1, infobox_text, re.IGNORECASE)
        if match1:
            print(f"✓ Pattern 1 MATCH: year={match1.group(1)}, month={match1.group(2)}, day={match1.group(3)}")
        else:
            print("✗ Pattern 1 NO MATCH")
        
        # Pattern 2: | birth_date = ...
        pattern2 = r'\|\s*birth_date\s*=\s*([^\|\n}]+)'
        match2 = re.search(pattern2, infobox_text, re.IGNORECASE)
        if match2:
            print(f"✓ Pattern 2 MATCH: {match2.group(1)[:100]}")
        else:
            print("✗ Pattern 2 NO MATCH")
        
        # Pattern 3: | birth_place = ...
        pattern3 = r'\|\s*birth_place\s*=\s*([^\|\n}]+)'
        match3 = re.search(pattern3, infobox_text, re.IGNORECASE)
        if match3:
            print(f"✓ Pattern 3 MATCH: {match3.group(1)[:100]}")
        else:
            print("✗ Pattern 3 NO MATCH")
    else:
        print("No infobox found!")
else:
    print("Failed to get page content")

