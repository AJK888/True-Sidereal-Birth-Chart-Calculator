#!/usr/bin/env python3
"""Test the actual patterns against the real text."""

import re

# Real examples from the terminal output
test_cases = [
    ("Leonardo da Vinci", "{{birth date|df=yes|1452|04|15}}"),
    ("William Shakespeare", "{{circa|{{birth date|df=yes|1564|04|23}}}}"),
    ("Isaac Newton", "{{Birth date|df=y|1643|01|04}}"),
]

def test_patterns(text):
    """Test all patterns."""
    print(f"\nTesting: {text}")
    
    # Pattern 1: nested
    p1 = re.search(r'\{\{circa\s*\|\s*\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', text, re.IGNORECASE)
    print(f"  Pattern 1 (nested): {'MATCH' if p1 else 'NO MATCH'}")
    if p1:
        print(f"    Groups: year={p1.group(1)}, month={p1.group(2)}, day={p1.group(3)}")
    
    # Pattern 2: lowercase with df
    p2 = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', text, re.IGNORECASE)
    print(f"  Pattern 2 (lowercase with df): {'MATCH' if p2 else 'NO MATCH'}")
    if p2:
        print(f"    Groups: year={p2.group(1)}, month={p2.group(2)}, day={p2.group(3)}")
    
    # Pattern 3: capital B with df
    p3 = re.search(r'\{\{Birth date\s*\|\s*df\s*=\s*(?:yes|y)\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', text, re.IGNORECASE)
    print(f"  Pattern 3 (capital B with df): {'MATCH' if p3 else 'NO MATCH'}")
    if p3:
        print(f"    Groups: year={p3.group(1)}, month={p3.group(2)}, day={p3.group(3)}")

for name, text in test_cases:
    print(f"\n{'='*60}")
    print(f"{name}")
    print('='*60)
    test_patterns(text)

