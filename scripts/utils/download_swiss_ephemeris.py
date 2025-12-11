"""
Download missing Swiss Ephemeris files for asteroid calculations.
"""
import os
import requests
from pathlib import Path

# Swiss Ephemeris files are available from astro.com
# The seas_12.se1 file contains asteroid data

BASE_DIR = Path(__file__).parent.parent
EPHE_DIR = BASE_DIR / "swiss_ephemeris"

def download_file(url: str, filepath: Path):
    """Download a file from URL."""
    print(f"Downloading {filepath.name}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"✓ Downloaded {filepath.name}")

def main():
    """Download missing Swiss Ephemeris files."""
    EPHE_DIR.mkdir(exist_ok=True)
    
    # Swiss Ephemeris files from astro.com
    # Note: These are large files (~50MB each)
    files_to_download = {
        "seas_12.se1": "https://www.astro.com/swisseph/swephinfo_e.htm",  # This is just the info page
    }
    
    print("=" * 70)
    print("SWISS EPHEMERIS FILE DOWNLOADER")
    print("=" * 70)
    print()
    print("Swiss Ephemeris files are available from:")
    print("1. https://www.astro.com/swisseph/swephinfo_e.htm")
    print("2. Or search for 'Swiss Ephemeris download'")
    print()
    print("The file 'seas_12.se1' is needed for asteroid calculations.")
    print("You can download it manually and place it in:")
    print(f"  {EPHE_DIR}")
    print()
    print("Alternatively, the 'seas_18.se1' file you have should work")
    print("for dates 1800-2100. The error might be a version issue.")
    print()
    print("=" * 70)

if __name__ == "__main__":
    main()

