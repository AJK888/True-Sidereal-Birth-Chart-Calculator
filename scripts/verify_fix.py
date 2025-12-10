#!/usr/bin/env python3
"""Verify the fix works by testing with Bruce Lee."""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Starting test...", file=sys.stderr)

try:
    from scripts.scrape_and_calculate_5000 import get_infobox_data
    print("Import successful", file=sys.stderr)
    
    result = get_infobox_data('Bruce_Lee')
    print("Function call complete", file=sys.stderr)
    
    output = {
        "success": bool(result),
        "has_birth_date": bool(result.get('birth_date')) if result else False,
        "has_birth_location": bool(result.get('birth_location')) if result else False,
        "birth_date": result.get('birth_date') if result else None,
        "birth_location": result.get('birth_location') if result else None,
        "would_pass": bool(
            result and 
            result.get('birth_date') and 
            result.get('birth_location') and
            result.get('birth_date', {}).get('year') and
            result.get('birth_date', {}).get('month') and
            result.get('birth_date', {}).get('day')
        ) if result else False
    }
    
    with open('verify_results.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(json.dumps(output, indent=2, default=str))
    
except Exception as e:
    error_output = {"error": str(e), "type": type(e).__name__}
    with open('verify_results.json', 'w') as f:
        json.dump(error_output, f, indent=2)
    print(json.dumps(error_output, indent=2))
    import traceback
    traceback.print_exc()

