"""
Fix Database Issues Script

This script fixes common data quality issues:
1. Removes ascendant data for people with unknown birth time
2. Removes duplicate records (keeps the first one)
3. Updates chart_data_json to remove ascendant data when unknown_time=True
"""

import os
import sys
import json
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db
from sqlalchemy import func
from natal_chart import calculate_numerology, get_chinese_zodiac_and_element


def fix_ascendants_for_unknown_time(db):
    """Remove ascendant data for people with unknown_time=True."""
    print("=" * 80)
    print("FIXING ASCENDANTS FOR UNKNOWN BIRTH TIME")
    print("=" * 80)
    
    # Find ALL records with unknown_time=True (need to check chart_data_json too)
    all_unknown_time_records = db.query(FamousPerson).filter(
        FamousPerson.unknown_time == True
    ).all()
    
    print(f"\nChecking {len(all_unknown_time_records)} records with unknown_time=True...")
    
    fixed_count = 0
    fixed_in_json = 0
    fixed_in_columns = 0
    
    for record in all_unknown_time_records:
        needs_fix = False
        
        # Check chart_data_json for ascendant data (rising sign columns have been removed)
        if record.chart_data_json:
            try:
                chart_data = json.loads(record.chart_data_json)
                updated = False
                
                # Check and remove ascendant from sidereal positions
                sidereal_positions = chart_data.get("sidereal_major_positions", [])
                original_count = len(sidereal_positions)
                chart_data["sidereal_major_positions"] = [
                    p for p in sidereal_positions 
                    if p.get("name") not in ["Ascendant", "Rising Sign"]
                ]
                if len(chart_data["sidereal_major_positions"]) < original_count:
                    updated = True
                
                # Check and remove ascendant from tropical positions
                tropical_positions = chart_data.get("tropical_major_positions", [])
                original_count = len(tropical_positions)
                chart_data["tropical_major_positions"] = [
                    p for p in tropical_positions 
                    if p.get("name") not in ["Ascendant", "Rising Sign"]
                ]
                if len(chart_data["tropical_major_positions"]) < original_count:
                    updated = True
                
                if updated:
                    record.chart_data_json = json.dumps(chart_data)
                    fixed_in_json += 1
                    needs_fix = True
                
            except (json.JSONDecodeError, Exception) as e:
                print(f"    Warning: Could not update chart_data_json for {record.name}: {e}")
        
        if needs_fix:
            fixed_count += 1
            if fixed_count <= 10:  # Show first 10
                print(f"  Fixed: {record.name} (ID: {record.id})")
            elif fixed_count == 11:
                print(f"  ... (fixing remaining records silently)")
    
    if fixed_count > 0:
        db.commit()
        print(f"\n✓ Fixed {fixed_count} records:")
        print(f"  - Fixed ascendant in chart_data_json: {fixed_in_json}")
    else:
        print("\n✓ No records needed fixing")
    
    return fixed_count


def populate_missing_numerology(db):
    """Extract and populate missing numerology data from chart_data_json to database columns.
    If data is missing or "N/A" in both places, recalculate from birth date."""
    print("\n" + "=" * 80)
    print("POPULATING MISSING NUMEROLOGY DATA")
    print("=" * 80)
    
    # Find ALL records to check (missing or "N/A" values)
    all_records = db.query(FamousPerson).all()
    
    print(f"\nChecking {len(all_records)} records for missing or N/A numerology data...")
    
    fixed_count = 0
    recalculated_count = 0
    
    for record in all_records:
        # Need birth date to calculate numerology
        if not all([record.birth_year, record.birth_month, record.birth_day]):
            continue
        
        updated = False
        needs_recalculation = False
        
        # Check if we need to fix life_path_number
        needs_life_path = (not record.life_path_number or 
                          record.life_path_number.upper() == "N/A")
        
        # Check if we need to fix day_number
        needs_day_number = (not record.day_number or 
                           record.day_number.upper() == "N/A")
        
        # Check if we need to fix Chinese zodiac
        needs_chinese = (not record.chinese_zodiac_animal or record.chinese_zodiac_animal.upper() == "N/A")
        
        # First, try to extract from chart_data_json
        if record.chart_data_json:
            try:
                chart_data = json.loads(record.chart_data_json)
                numerology = chart_data.get("numerology_analysis", {})
                
                # Extract life_path_number from JSON
                if needs_life_path:
                    life_path_value = numerology.get("life_path_number")
                    if life_path_value and life_path_value != "N/A":
                        record.life_path_number = str(life_path_value)
                        updated = True
                    else:
                        needs_recalculation = True
                
                # Extract day_number from JSON
                if needs_day_number:
                    day_number_value = numerology.get("day_number")
                    if day_number_value and day_number_value != "N/A":
                        record.day_number = str(day_number_value)
                        updated = True
                    else:
                        needs_recalculation = True
                
                # Extract Chinese zodiac from JSON
                if needs_chinese:
                    chinese_zodiac_str = chart_data.get("chinese_zodiac", "")
                    if chinese_zodiac_str and chinese_zodiac_str != "N/A":
                        parts = chinese_zodiac_str.strip().split()
                        if len(parts) >= 2:
                            if needs_chinese:
                                if not record.chinese_zodiac_animal or record.chinese_zodiac_animal.upper() == "N/A":
                                    record.chinese_zodiac_animal = parts[1]
                                    updated = True
                            else:
                                needs_recalculation = True
                    else:
                        needs_recalculation = True
            except (json.JSONDecodeError, Exception):
                # If JSON parsing fails, recalculate
                needs_recalculation = True
        else:
            # No JSON, need to recalculate
            needs_recalculation = True
        
        # If still missing or "N/A", recalculate from birth date
        if needs_recalculation or needs_life_path or needs_day_number or needs_chinese:
            try:
                numerology_result = calculate_numerology(
                    record.birth_day, record.birth_month, record.birth_year
                )
                
                if needs_life_path:
                    # The function returns "life_path" (not "life_path_number")
                    life_path = numerology_result.get("life_path")
                    if life_path:
                        record.life_path_number = str(life_path)
                        updated = True
                
                if needs_day_number:
                    day_num = numerology_result.get("day_number")
                    if day_num:
                        record.day_number = str(day_num)
                        updated = True
                
                if needs_chinese:
                    chinese_result = get_chinese_zodiac_and_element(
                        record.birth_year, record.birth_month, record.birth_day
                    )
                    if chinese_result:
                        if not record.chinese_zodiac_animal or record.chinese_zodiac_animal.upper() == "N/A":
                            record.chinese_zodiac_animal = chinese_result.get("animal")
                            updated = True
                
                if updated:
                    recalculated_count += 1
            except Exception as e:
                # Skip records that can't be calculated
                continue
        
        if updated:
            fixed_count += 1
            if fixed_count <= 10:
                print(f"  Fixed: {record.name} (ID: {record.id})")
            elif fixed_count == 11:
                print(f"  ... (fixing remaining records silently)")
    
    if fixed_count > 0:
        db.commit()
        print(f"\n✓ Populated numerology data for {fixed_count} records")
        if recalculated_count > 0:
            print(f"  - Recalculated from birth date: {recalculated_count} records")
    else:
        print("\n✓ No records needed fixing")
    
    return fixed_count


def remove_duplicates(db):
    """Remove duplicate records, keeping the first one."""
    print("\n" + "=" * 80)
    print("REMOVING DUPLICATES")
    print("=" * 80)
    
    # Find duplicate names
    duplicates = db.query(
        FamousPerson.name,
        func.count(FamousPerson.id).label('count')
    ).group_by(FamousPerson.name).having(func.count(FamousPerson.id) > 1).all()
    
    if not duplicates:
        print("\n✓ No duplicates found")
        return 0
    
    print(f"\nFound {len(duplicates)} duplicate name(s)")
    
    removed_count = 0
    for name, count in duplicates:
        print(f"\n  Duplicate: '{name}' ({count} records)")
        
        # Get all records with this name, ordered by ID (keep the first one)
        records = db.query(FamousPerson).filter(
            FamousPerson.name == name
        ).order_by(FamousPerson.id).all()
        
        if len(records) > 1:
            # Keep the first record (lowest ID)
            keep_record = records[0]
            remove_records = records[1:]
            
            print(f"    Keeping: ID {keep_record.id} (created: {keep_record.created_at})")
            
            # Check which record has more complete data
            keep_completeness = sum([
                1 if keep_record.sun_sign_sidereal else 0,
                1 if keep_record.sun_sign_tropical else 0,
                1 if keep_record.moon_sign_sidereal else 0,
                1 if keep_record.moon_sign_tropical else 0,
                1 if keep_record.life_path_number else 0,
                1 if keep_record.chinese_zodiac_animal else 0,
            ])
            
            for remove_record in remove_records:
                remove_completeness = sum([
                    1 if remove_record.sun_sign_sidereal else 0,
                    1 if remove_record.sun_sign_tropical else 0,
                    1 if remove_record.moon_sign_sidereal else 0,
                    1 if remove_record.moon_sign_tropical else 0,
                    1 if remove_record.life_path_number else 0,
                    1 if remove_record.chinese_zodiac_animal else 0,
                ])
                
                # If the record to remove has more complete data, swap them
                if remove_completeness > keep_completeness:
                    print(f"    Note: ID {remove_record.id} has more complete data, keeping it instead")
                    keep_record = remove_record
                    remove_records = [r for r in records if r.id != remove_record.id]
                    break
            
            # Delete the records to remove
            for remove_record in remove_records:
                print(f"    Removing: ID {remove_record.id}")
                db.delete(remove_record)
                removed_count += 1
    
    if removed_count > 0:
        db.commit()
        print(f"\n✓ Removed {removed_count} duplicate record(s)")
    else:
        print("\n✓ No duplicates removed")
    
    return removed_count


def main():
    """Main function to fix database issues."""
    print("=" * 80)
    print("DATABASE FIX SCRIPT")
    print("=" * 80)
    print(f"\nThis script will:")
    print("  1. Remove ascendant data for people with unknown birth time (from columns and chart_data_json)")
    print("  2. Populate missing numerology data from chart_data_json to database columns")
    print("  3. Remove duplicate records (keeping the most complete one)")
    print("\n⚠️  This will modify your database!")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Aborted.")
        return
    
    print("\nInitializing database connection...")
    init_db()
    db = SessionLocal()
    
    try:
        # Fix ascendants
        ascendant_fixes = fix_ascendants_for_unknown_time(db)
        
        # Populate missing numerology
        numerology_fixes = populate_missing_numerology(db)
        
        # Remove duplicates
        duplicate_removals = remove_duplicates(db)
        
        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Ascendant fixes: {ascendant_fixes}")
        print(f"Numerology populated: {numerology_fixes}")
        print(f"Duplicates removed: {duplicate_removals}")
        print(f"Total fixes: {ascendant_fixes + numerology_fixes + duplicate_removals}")
        print("\n✓ Database fix complete!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()

