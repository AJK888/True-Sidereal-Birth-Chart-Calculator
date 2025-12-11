"""Export all famous people data to CSV file"""

import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

def export_to_csv(output_file=None):
    """Export all famous people records to CSV."""
    
    # Set output file path
    if output_file is None:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_file = os.path.join(script_dir, "famous_people_export.csv")
    
    db = SessionLocal()
    
    # Get all records
    records = db.query(FamousPerson).order_by(FamousPerson.id).all()
    
    print(f"Exporting {len(records)} records to {output_file}...")
    print(f"Found {len(records)} records in database")
    
    # Define CSV columns
    fieldnames = [
        'id',
        'name',
        'wikipedia_url',
        'occupation',
        'birth_year',
        'birth_month',
        'birth_day',
        'birth_hour',
        'birth_minute',
        'birth_location',
        'unknown_time',
        'sun_sign_sidereal',
        'sun_sign_tropical',
        'moon_sign_sidereal',
        'moon_sign_tropical',
        'life_path_number',
        'day_number',
        'chinese_zodiac_animal',
        'page_views',
        'created_at',
        'updated_at',
        'has_chart_data_json',  # Boolean flag instead of full JSON
        'has_planetary_placements_json',  # Boolean flag
        'has_top_aspects_json'  # Boolean flag
    ]
    
    # Write to CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in records:
            row = {
                'id': record.id,
                'name': record.name or '',
                'wikipedia_url': record.wikipedia_url or '',
                'occupation': record.occupation or '',
                'birth_year': record.birth_year or '',
                'birth_month': record.birth_month or '',
                'birth_day': record.birth_day or '',
                'birth_hour': record.birth_hour if record.birth_hour is not None else '',
                'birth_minute': record.birth_minute if record.birth_minute is not None else '',
                'birth_location': record.birth_location or '',
                'unknown_time': 'True' if record.unknown_time else 'False',
                'sun_sign_sidereal': record.sun_sign_sidereal or '',
                'sun_sign_tropical': record.sun_sign_tropical or '',
                'moon_sign_sidereal': record.moon_sign_sidereal or '',
                'moon_sign_tropical': record.moon_sign_tropical or '',
                'life_path_number': record.life_path_number or '',
                'day_number': record.day_number or '',
                'chinese_zodiac_animal': record.chinese_zodiac_animal or '',
                'page_views': record.page_views if record.page_views is not None else '',
                'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S') if record.created_at else '',
                'updated_at': record.updated_at.strftime('%Y-%m-%d %H:%M:%S') if record.updated_at else '',
                'has_chart_data_json': 'Yes' if record.chart_data_json else 'No',
                'has_planetary_placements_json': 'Yes' if hasattr(record, 'planetary_placements_json') and record.planetary_placements_json else 'No',
                'has_top_aspects_json': 'Yes' if hasattr(record, 'top_aspects_json') and record.top_aspects_json else 'No'
            }
            writer.writerow(row)
    
    print(f"Finished writing {len(records)} rows to CSV")
    
    db.close()
    
    abs_path = os.path.abspath(output_file)
    print(f"✓ Successfully exported {len(records)} records to {output_file}")
    print(f"  File location: {abs_path}")
    print(f"  File exists: {os.path.exists(output_file)}")
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"  File size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    
    return output_file

if __name__ == "__main__":
    try:
        output_file = export_to_csv()
        print(f"\nCSV export complete: {output_file}")
    except Exception as e:
        print(f"\n✗ Error exporting CSV: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

