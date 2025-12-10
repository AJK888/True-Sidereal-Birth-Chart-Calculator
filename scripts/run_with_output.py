"""
Wrapper to run scraper and show output in real-time
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("RUNNING WIKIPEDIA SCRAPER")
print("=" * 70)
print()

# Run the script and capture output in real-time
process = subprocess.Popen(
    [sys.executable, "scripts/scrape_wikipedia_famous_people_fixed.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
)

# Print output as it comes
for line in process.stdout:
    print(line, end='', flush=True)

process.wait()

print()
print("=" * 70)
print(f"Script completed with exit code: {process.returncode}")
print("=" * 70)

# Check for output files
if os.path.exists("famous_people_data.json"):
    print("\n✓ Output file created: famous_people_data.json")
    with open("famous_people_data.json", 'r', encoding='utf-8') as f:
        data = f.read()
        print(f"  File size: {len(data)} bytes")
        if len(data) > 0:
            import json
            try:
                people = json.loads(data)
                print(f"  People found: {len(people)}")
                for person in people[:3]:
                    print(f"    - {person.get('name')}: {person.get('birth_date')}")
            except:
                print("  (Could not parse JSON)")
else:
    print("\n✗ Output file NOT created")

if os.path.exists("scraper_run.log"):
    print("\n✓ Log file created: scraper_run.log")
    with open("scraper_run.log", 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(f"  Log lines: {len(lines)}")
        print("\n  Last 10 lines of log:")
        for line in lines[-10:]:
            print(f"    {line.rstrip()}")

