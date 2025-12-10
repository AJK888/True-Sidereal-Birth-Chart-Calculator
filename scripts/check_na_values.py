"""Quick script to check for N/A values in the database"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

db = SessionLocal()

# Find records with N/A values
na_life_path = db.query(FamousPerson).filter(
    (FamousPerson.life_path_number == 'N/A') | 
    (FamousPerson.life_path_number == 'n/a')
).limit(5).all()

with open('na_check_output.txt', 'w') as f:
    f.write(f"Found {len(na_life_path)} records with N/A life_path_number (showing first 5):\n")
    for record in na_life_path:
        f.write(f"\n  Name: {record.name}\n")
        f.write(f"  life_path_number: {record.life_path_number}\n")
        f.write(f"  day_number: {record.day_number}\n")
        f.write(f"  Has chart_data_json: {bool(record.chart_data_json)}\n")
        
        if record.chart_data_json:
            try:
                chart = json.loads(record.chart_data_json)
                numerology = chart.get('numerology_analysis', {})
                f.write(f"  JSON life_path_number: {numerology.get('life_path_number')}\n")
                f.write(f"  JSON day_number: {numerology.get('day_number')}\n")
            except Exception as e:
                f.write(f"  Error parsing JSON: {e}\n")

print(f"Output written to na_check_output.txt")
db.close()

