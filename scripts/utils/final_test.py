import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.scrape_and_calculate_5000 import get_infobox_data

test_result = {}
try:
    result = get_infobox_data('Bruce_Lee')
    test_result = {
        "test": "Bruce_Lee",
        "success": bool(result),
        "has_birth_date": bool(result.get('birth_date')) if result else False,
        "has_birth_location": bool(result.get('birth_location')) if result else False,
        "birth_date": result.get('birth_date') if result else None,
        "birth_location": result.get('birth_location') if result else None,
        "would_pass_filter": bool(
            result and 
            result.get('birth_date') and 
            result.get('birth_location') and
            result.get('birth_date', {}).get('year') and
            result.get('birth_date', {}).get('month') and
            result.get('birth_date', {}).get('day')
        ) if result else False
    }
except Exception as e:
    test_result = {"error": str(e), "type": type(e).__name__}

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'FINAL_TEST_RESULT.json'), 'w') as f:
    json.dump(test_result, f, indent=2, default=str)

