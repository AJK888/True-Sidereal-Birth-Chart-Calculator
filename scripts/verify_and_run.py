"""
Verify dependencies and run scraper with visible output
"""
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 70)
print("VERIFYING DEPENDENCIES")
print("=" * 70)

# Check dependencies
missing = []
try:
    import wikipediaapi
    print("✓ wikipedia-api installed")
except ImportError:
    print("✗ wikipedia-api NOT installed")
    missing.append("wikipedia-api")

try:
    import requests
    print("✓ requests installed")
except ImportError:
    print("✗ requests NOT installed")
    missing.append("requests")

if missing:
    print(f"\n⚠ Missing packages: {', '.join(missing)}")
    print("Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
    print("✓ Packages installed")
    print("\nPlease run the script again:")
    print("  python scripts/scrape_wikipedia_famous_people_fixed.py")
    sys.exit(0)

print("\n" + "=" * 70)
print("RUNNING SCRAPER")
print("=" * 70)
print()

# Run the actual scraper
sys.path.insert(0, '.')
from scripts.scrape_wikipedia_famous_people_fixed import main

try:
    main()
    print("\n" + "=" * 70)
    print("✓ SCRAPER COMPLETED")
    print("=" * 70)
except KeyboardInterrupt:
    print("\n\n⚠ Script interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\n\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

