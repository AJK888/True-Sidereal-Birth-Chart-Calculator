#!/usr/bin/env python3
"""Test the regex patterns against the actual formats."""

import re

# Test cases from the actual Wikipedia infoboxes
test_cases = [
    ("Leonardo da Vinci", "{{birth date|df=yes|1452|04|15}}"),
    ("William Shakespeare", "{{circa|{{birth date|df=yes|1564|04|23}}}}"),
    ("Isaac Newton", "{{Birth date|df=y|1643|01|04}}"),
    ("Albert Einstein", "{{birth date|1879|3|14}}"),  # This one works
]

month_map = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2,
    'march': 3, 'mar': 3, 'april': 4, 'apr': 4,
    'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11,
    'december': 12, 'dec': 12
}

def test_parse_birth_date(infobox_text):
    """Test the parsing function."""
    
    # Pattern 1: Handle nested templates
    nested_pattern = re.search(r'\{\{circa\s*\|\s*\{\{birth date(?:\s+and\s+age)?\s*\|\s*(?:df\s*=\s*(?:yes|y)\s*\|)?(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if nested_pattern:
        print(f"  Pattern 1 (nested) MATCH: year={nested_pattern.group(1)}, month={nested_pattern.group(2)}, day={nested_pattern.group(3)}")
        return True
    
    # Pattern 2: {{birth date|df=yes|1452|04|15}}
    birth_date_with_df = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*(?:df\s*=\s*(?:yes|y)\s*\|)?(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_with_df:
        print(f"  Pattern 2 (with df) MATCH: year={birth_date_with_df.group(1)}, month={birth_date_with_df.group(2)}, day={birth_date_with_df.group(3)}")
        return True
    
    # Pattern 3: Standard format
    birth_date_template = re.search(r'\{\{birth date(?:\s+and\s+age)?\s*\|\s*(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_template:
        print(f"  Pattern 3 (standard) MATCH: year={birth_date_template.group(1)}, month={birth_date_template.group(2)}, day={birth_date_template.group(3)}")
        return True
    
    # Pattern 4: Capital B
    birth_date_capital = re.search(r'\{\{Birth date\s*\|\s*(?:df\s*=\s*(?:yes|y)\s*\|)?(\d{4})\s*\|\s*(\d{1,2})\s*\|\s*(\d{1,2})', infobox_text, re.IGNORECASE)
    if birth_date_capital:
        print(f"  Pattern 4 (capital B) MATCH: year={birth_date_capital.group(1)}, month={birth_date_capital.group(2)}, day={birth_date_capital.group(3)}")
        return True
    
    print("  NO MATCH")
    return False

print("Testing regex patterns:")
print("=" * 60)
for name, text in test_cases:
    print(f"\n{name}:")
    print(f"  Input: {text}")
    test_parse_birth_date(text)

