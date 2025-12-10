"""
Run scraper and show progress by reading output file
"""
import sys
import os
import time
import subprocess
import json

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Starting Wikipedia scraper...")
print("This will take about 3-5 seconds for 5 people...")
print()

# Run the script
proc = subprocess.Popen(
    [sys.executable, "scripts/scrape_wikipedia_famous_people_fixed.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# Wait for completion
stdout, stderr = proc.communicate()

print("=" * 70)
print("SCRIPT OUTPUT:")
print("=" * 70)
if stdout:
    print(stdout)
else:
    print("(No stdout captured)")

print()
print("=" * 70)
print("CHECKING OUTPUT FILES:")
print("=" * 70)

# Check for JSON file
if os.path.exists("famous_people_data.json"):
    print("\n✓ famous_people_data.json exists")
    try:
        with open("famous_people_data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"  Found {len(data)} people:")
            for person in data:
                name = person.get('name', 'Unknown')
                bd = person.get('birth_date', {})
                loc = person.get('birth_location', 'Unknown')
                print(f"    • {name}")
                if bd:
                    print(f"      Born: {bd.get('month')}/{bd.get('day')}/{bd.get('year')}")
                print(f"      Location: {loc}")
                print()
    except Exception as e:
        print(f"  Error reading JSON: {e}")
else:
    print("\n✗ famous_people_data.json NOT found")

# Check for log file
if os.path.exists("scraper_run.log"):
    print("\n✓ scraper_run.log exists")
    try:
        with open("scraper_run.log", 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"  Log size: {len(content)} characters")
            print("\n  Log content:")
            print("-" * 70)
            print(content)
            print("-" * 70)
    except Exception as e:
        print(f"  Error reading log: {e}")
else:
    print("\n✗ scraper_run.log NOT found")

print(f"\nScript exit code: {proc.returncode}")

