#!/usr/bin/env python3
"""Test script to see what format Wikipedia API returns."""

import wikipediaapi
import re

wiki = wikipediaapi.Wikipedia('en', user_agent='Test/1.0', extract_format=wikipediaapi.ExtractFormat.WIKI)
page = wiki.page('Albert Einstein')

print("=" * 60)
print("Testing Wikipedia API format")
print("=" * 60)
print(f"Page exists: {page.exists()}")
print(f"Text length: {len(page.text)}")

text = page.text
start = text.find('{{Infobox')
print(f"\nInfobox found at position: {start}")

if start != -1:
    infobox_text = text[start:start+2000]
    print("\n" + "=" * 60)
    print("INFOBOX TEXT (first 2000 chars):")
    print("=" * 60)
    print(infobox_text)
    
    # Test our regex patterns
    print("\n" + "=" * 60)
    print("TESTING BIRTH DATE PATTERNS:")
    print("=" * 60)
    
    # Pattern 1: {{birth date|1879|3|14}}
    pattern1 = r'\{\{birth date(?:\s+and\s+age)?\|(\d{4})\|(\d{1,2})\|(\d{1,2})'
    match1 = re.search(pattern1, infobox_text, re.IGNORECASE)
    print(f"Pattern 1 ({{{{birth date|year|month|day}}}}): {match1.groups() if match1 else 'NO MATCH'}")
    
    # Pattern 2: | birth_date = ...
    pattern2 = r'\|\s*birth_date\s*=\s*([^\|\n}]+)'
    match2 = re.search(pattern2, infobox_text, re.IGNORECASE)
    print(f"Pattern 2 (| birth_date = ...): {match2.group(1) if match2 else 'NO MATCH'}")
    
    # Pattern 3: | birth_place = ...
    pattern3 = r'\|\s*birth_place\s*=\s*([^\|\n}]+)'
    match3 = re.search(pattern3, infobox_text, re.IGNORECASE)
    print(f"Pattern 3 (| birth_place = ...): {match3.group(1) if match3 else 'NO MATCH'}")
else:
    print("\nNo infobox found. First 2000 chars:")
    print(text[:2000])

