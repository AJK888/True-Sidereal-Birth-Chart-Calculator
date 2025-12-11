"""Copy seas_18.se1 to seas_12.se1 as a workaround."""
import shutil
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
EPHE_DIR = BASE_DIR / "swiss_ephemeris"
SOURCE = EPHE_DIR / "seas_18.se1"
TARGET = EPHE_DIR / "seas_12.se1"

if __name__ == "__main__":
    if not SOURCE.exists():
        print(f"Error: {SOURCE} not found!")
        exit(1)
    
    if TARGET.exists():
        print(f"{TARGET.name} already exists. Skipping.")
    else:
        try:
            shutil.copy(SOURCE, TARGET)
            print(f"✓ Created {TARGET.name} (copy of {SOURCE.name})")
            print("Note: This is a workaround. For best results, download the actual seas_12.se1 file.")
        except Exception as e:
            print(f"Error copying file: {e}")
            exit(1)

