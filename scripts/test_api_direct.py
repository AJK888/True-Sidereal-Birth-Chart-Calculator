#!/usr/bin/env python3
"""Test Wikipedia API directly to see the format."""

import requests
import re
import json

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
headers = {"User-Agent": "SynthesisAstrology/1.0 (contact@synthesisastrology.com)"}

print("Fetching Albert Einstein page from Wikipedia API...")
response = requests.get(api_url, params=params, headers=headers, timeout=10)
data = response.json()

pages = data.get("query", {}).get("pages", [])
if pages and "revisions" in pages[0]:
    text = pages[0]["revisions"][0]["slots"]["main"]["content"]
    print(f"✓ Got {len(text)} characters of wiki markup\n")
    
    # Find infobox
    start = text.find('{{Infobox')
    print(f"Infobox found at position: {start}\n")
    
    if start != -1:
        infobox_text = text[start:start+3000]
        
        # Write to file for inspection
        with open('test_infobox_sample.txt', 'w', encoding='utf-8') as f:
            f.write(infobox_text)
        print("✓ Saved infobox sample to test_infobox_sample.txt\n")
        
        # Test our patterns
        print("Testing birth date patterns:")
        print("-" * 60)
        
        # Pattern 1: {{birth date|1879|3|14}}
        pattern1 = r'\{\{birth date(?:\s+and\s+age)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})'
        match1 = re.search(pattern1, infobox_text, re.IGNORECASE)
        if match1:
            print(f"✓ Pattern 1 MATCH: year={match1.group(1)}, month={match1.group(2)}, day={match1.group(3)}")
        else:
            print("✗ Pattern 1 NO MATCH")
            # Show what we're looking for
            print(f"   Looking for: {{birth date|YYYY|M|D}}")
            # Show what's actually there
            birth_date_section = re.search(r'birth_date\s*=\s*[^\|\n}]+', infobox_text, re.IGNORECASE)
            if birth_date_section:
                print(f"   Found: {birth_date_section.group(0)[:100]}")
        
        # Pattern 2: | birth_date = 14 March 1879
        pattern2 = r'\|\s*birth_date\s*=\s*(\d{1,2})\s+(\w+)\s+(\d{4})'
        match2 = re.search(pattern2, infobox_text, re.IGNORECASE)
        if match2:
            print(f"✓ Pattern 2 MATCH: day={match2.group(1)}, month={match2.group(2)}, year={match2.group(3)}")
        else:
            print("✗ Pattern 2 NO MATCH")
        
        # Pattern 3: | birth_place = ...
        pattern3 = r'\|\s*birth_place\s*=\s*([^\|\n}]+)'
        match3 = re.search(pattern3, infobox_text, re.IGNORECASE)
        if match3:
            place = match3.group(1).strip()
            place = re.sub(r'\[\[([^\]]+)\]\]', r'\1', place)
            print(f"✓ Pattern 3 MATCH: {place[:100]}")
        else:
            print("✗ Pattern 3 NO MATCH")
        
        print("\n" + "="*60)
        print("First 1000 characters of infobox:")
        print("="*60)
        print(infobox_text[:1000])
    else:
        print("✗ No infobox found!")
        print("First 2000 characters of page:")
        print(text[:2000])
else:
    print("✗ Failed to get page content")
    print(json.dumps(data, indent=2)[:500])

