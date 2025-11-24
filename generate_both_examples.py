#!/usr/bin/env python3
"""Generate both Elon Musk and Barack Obama examples sequentially"""
import subprocess
import sys
import time

def run_example(name, year, month, day, hour, minute, location):
    """Run a single example generation"""
    print(f"\n{'='*60}")
    print(f"Generating {name} example...")
    print(f"{'='*60}\n")
    
    cmd = [
        sys.executable,
        "create_single_example.py",
        "--name", name,
        "--year", str(year),
        "--month", str(month),
        "--day", str(day),
        "--hour", str(hour),
        "--minute", str(minute),
        "--location", location
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0

if __name__ == "__main__":
    print("="*60)
    print("Generating Example Reports")
    print("="*60)
    
    # Elon Musk
    success1 = run_example("Elon Musk", 1971, 6, 28, 7, 30, "Pretoria, South Africa")
    
    if not success1:
        print("\n❌ Failed to generate Elon Musk example")
        sys.exit(1)
    
    print("\n⏳ Waiting 60 seconds before next request to avoid rate limits...")
    time.sleep(60)
    
    # Barack Obama
    success2 = run_example("Barack Obama", 1961, 8, 4, 19, 24, "Honolulu, Hawaii, USA")
    
    if not success2:
        print("\n❌ Failed to generate Barack Obama example")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("✓ Both examples generated successfully!")
    print("="*60)
    print("\nFiles saved to: True-Sidereal-Birth-Chart-Calculator/examples/data/")
    print("  - elon-musk.json")
    print("  - barack-obama.json")

