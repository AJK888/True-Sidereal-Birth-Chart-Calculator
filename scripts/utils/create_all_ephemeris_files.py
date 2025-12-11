"""Create all possible Swiss Ephemeris asteroid files by copying seas_18.se1."""
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
EPHE_DIR = BASE_DIR / "swiss_ephemeris"
SOURCE = EPHE_DIR / "seas_18.se1"

# Swiss Ephemeris might look for these files based on date ranges
# We'll create copies for common ones (workaround for people born 1800-2100)
FILES_TO_CREATE = [
    "seas_06.se1",  # 600-700 (might be checked)
    "seas_12.se1",  # 1200-1300 (already exists, but ensure it's there)
    "seas_18.se1",  # 1800-2100 (original - already exists)
]

if __name__ == "__main__":
    if not SOURCE.exists():
        print(f"Error: {SOURCE} not found!")
        exit(1)
    
    print("=" * 70)
    print("CREATING SWISS EPHEMERIS ASTEROID FILES")
    print("=" * 70)
    print()
    
    created = 0
    skipped = 0
    
    for filename in FILES_TO_CREATE:
        target = EPHE_DIR / filename
        
        if target.exists():
            print(f"✓ {filename} already exists - skipping")
            skipped += 1
        else:
            try:
                shutil.copy(SOURCE, target)
                print(f"✓ Created {filename} (copy of seas_18.se1)")
                created += 1
            except Exception as e:
                print(f"✗ Failed to create {filename}: {e}")
    
    print()
    print("=" * 70)
    print(f"Summary: Created {created}, Skipped {skipped}")
    print("=" * 70)
    print()
    print("Note: These are copies of seas_18.se1 (1800-2100).")
    print("For historical dates, download the actual files from:")
    print("https://www.astro.com/swisseph/swephinfo_e.htm")
    print()

