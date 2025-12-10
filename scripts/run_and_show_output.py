"""
Run the scraper and capture all output to a file
"""
import sys
import os
import subprocess

# Change to script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(script_dir))

# Run the scraper and capture output
output_file = os.path.join(script_dir, "scraper_output.txt")

print("Running Wikipedia scraper...")
print(f"Output will be saved to: {output_file}")

with open(output_file, 'w', encoding='utf-8') as f:
    result = subprocess.run(
        [sys.executable, "scripts/scrape_wikipedia_famous_people_fixed.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8'
    )
    f.write(result.stdout)
    if result.returncode != 0:
        f.write(f"\n\nExit code: {result.returncode}")

print(f"\nScript completed. Check {output_file} for full output.")
print(f"Exit code: {result.returncode}")

# Also print first 50 lines
if os.path.exists(output_file):
    with open(output_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print("\n" + "="*60)
        print("First 50 lines of output:")
        print("="*60)
        for i, line in enumerate(lines[:50], 1):
            print(f"{i:3}: {line.rstrip()}")

