"""
Script to comment out old endpoint definitions in api.py that have been moved to routers.

This script adds comment markers to indicate endpoints have been moved.
Run this script, then manually verify and remove the commented code.
"""

import re

def comment_out_endpoint(file_path, endpoint_pattern, comment_text):
    """Comment out an endpoint definition."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the endpoint decorator
    pattern = rf'(@app\.(?:get|post|delete|put|api_route)\([^)]+\)\s*\n(?:@[^\n]+\n)*async def [^\n]+\([^)]*\):)'
    
    matches = list(re.finditer(pattern, content))
    for match in reversed(matches):  # Process in reverse to maintain positions
        if endpoint_pattern in match.group(0):
            start = match.start()
            # Add comment before the decorator
            commented = f"# {comment_text}\n# {match.group(0)}"
            content = content[:start] + commented + content[match.end():]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Commented out endpoints matching: {endpoint_pattern}")

if __name__ == "__main__":
    print("This script would comment out endpoints, but manual editing is safer.")
    print("Please manually comment out old endpoints using the markers already added.")

