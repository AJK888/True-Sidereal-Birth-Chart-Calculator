"""
Run scraper with verbose output to file
"""
import sys
import os
import json
from datetime import datetime

# Change to project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

progress_file = "scraper_progress.txt"

def log_progress(msg):
    """Write progress to file and print"""
    with open(progress_file, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime("%H:%M:%S")
        f.write(f"[{timestamp}] {msg}\n")
        f.flush()
    print(msg, flush=True)

# Clear previous progress
if os.path.exists(progress_file):
    os.remove(progress_file)

log_progress("=" * 70)
log_progress("STARTING WIKIPEDIA SCRAPER")
log_progress("=" * 70)

try:
    # Import and run
    sys.path.insert(0, '.')
    from scripts.scrape_wikipedia_famous_people_fixed import main
    
    log_progress("\nCalling main() function...")
    main()
    log_progress("\n✓ Script completed successfully!")
    
except Exception as e:
    log_progress(f"\n✗ ERROR: {e}")
    import traceback
    error_details = traceback.format_exc()
    log_progress(error_details)
    sys.exit(1)

# Check results
log_progress("\n" + "=" * 70)
log_progress("CHECKING RESULTS:")
log_progress("=" * 70)

if os.path.exists("famous_people_data.json"):
    log_progress("\n✓ Output file created!")
    try:
        with open("famous_people_data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
            log_progress(f"  Found {len(data)} people:")
            for person in data:
                name = person.get('name', 'Unknown')
                bd = person.get('birth_date', {})
                if bd:
                    log_progress(f"    • {name}: {bd.get('month')}/{bd.get('day')}/{bd.get('year')} in {person.get('birth_location', 'Unknown')}")
    except Exception as e:
        log_progress(f"  Error reading JSON: {e}")
else:
    log_progress("\n✗ Output file NOT created")

if os.path.exists("scraper_run.log"):
    log_progress("\n✓ Log file created!")
    with open("scraper_run.log", 'r', encoding='utf-8') as f:
        log_content = f.read()
        log_progress(f"  Log size: {len(log_content)} characters")

log_progress("\n" + "=" * 70)
log_progress("DONE")
log_progress("=" * 70)

