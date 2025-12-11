"""
Quality Control Script for Famous People Database

This script validates all entries in the famous_people table to ensure:
- Required fields are present
- Data is valid and consistent
- Chart calculations are correct
- No duplicates or inconsistencies
"""

import os
import sys
import json
import calendar
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db

# Valid zodiac signs (including Ophiuchus for sidereal astrology)
VALID_SIGNS = {
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    "Ophiuchus"  # 13th sign in sidereal astrology
}

# Valid Chinese zodiac animals
VALID_CHINESE_ANIMALS = {
    "Rat", "Ox", "Tiger", "Rabbit", "Dragon", "Snake",
    "Horse", "Goat", "Monkey", "Rooster", "Dog", "Pig"
}

# Valid Chinese zodiac elements
VALID_CHINESE_ELEMENTS = {"Wood", "Fire", "Earth", "Metal", "Water"}

# Valid life path numbers (1-9, 11, 22, 33, or Master Numbers with reduction like "33/6", "22/4")
def is_valid_life_path(life_path: str) -> bool:
    """Check if life path number is valid (supports master numbers with reduction)."""
    if not life_path:
        return False
    # Check simple numbers (1-9, 11, 22, 33)
    if life_path in {str(i) for i in range(1, 10)} | {"11", "22", "33"}:
        return True
    # Check master number format (e.g., "33/6", "22/4")
    if "/" in life_path:
        parts = life_path.split("/")
        if len(parts) == 2:
            master, reduced = parts[0].strip(), parts[1].strip()
            if master in {"11", "22", "33"} and reduced in {str(i) for i in range(1, 10)}:
                return True
    return False

# Valid day numbers (1-9, 11, 22, 33, or Master Numbers with reduction like "11/2", "22/4")
def is_valid_day_number(day_number: str) -> bool:
    """Check if day number is valid (supports master numbers with reduction)."""
    if not day_number:
        return False
    # Check simple numbers (1-9, 11, 22, 33)
    if day_number in {str(i) for i in range(1, 10)} | {"11", "22", "33"}:
        return True
    # Check master number format (e.g., "11/2", "22/4")
    if "/" in day_number:
        parts = day_number.split("/")
        if len(parts) == 2:
            master, reduced = parts[0].strip(), parts[1].strip()
            if master in {"11", "22", "33"} and reduced in {str(i) for i in range(1, 10)}:
                return True
    return False


class QualityControlReport:
    """Collects and reports quality control issues."""
    
    def __init__(self):
        self.issues = []
        self.stats = {
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "issues_by_type": defaultdict(int)
        }
    
    def add_issue(self, record_id: int, name: str, issue_type: str, message: str):
        """Add a quality control issue."""
        self.issues.append({
            "id": record_id,
            "name": name,
            "type": issue_type,
            "message": message
        })
        self.stats["issues_by_type"][issue_type] += 1
        self.stats["invalid_records"] += 1
    
    def print_report(self):
        """Print a formatted quality control report."""
        print("=" * 80)
        print("DATABASE QUALITY CONTROL REPORT")
        print("=" * 80)
        print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nTotal Records: {self.stats['total_records']}")
        print(f"Valid Records: {self.stats['valid_records']}")
        print(f"Records with Issues: {self.stats['invalid_records']}")
        
        if self.stats['invalid_records'] > 0:
            print(f"\nIssues by Type:")
            for issue_type, count in sorted(self.stats['issues_by_type'].items()):
                print(f"  - {issue_type}: {count}")
        
        if self.issues:
            print(f"\n{'=' * 80}")
            print("DETAILED ISSUES")
            print("=" * 80)
            
            # Group by type
            issues_by_type = defaultdict(list)
            for issue in self.issues:
                issues_by_type[issue['type']].append(issue)
            
            for issue_type, type_issues in sorted(issues_by_type.items()):
                print(f"\n{issue_type.upper()} ({len(type_issues)} issues):")
                print("-" * 80)
                for issue in type_issues[:20]:  # Show first 20 of each type
                    print(f"  ID {issue['id']:5d} | {issue['name'][:40]:40s} | {issue['message']}")
                if len(type_issues) > 20:
                    print(f"  ... and {len(type_issues) - 20} more")
        else:
            print("\n✓ No issues found! Database is clean.")
        
        print("\n" + "=" * 80)
    
    def save_report(self, filename: str = "qc_report.txt"):
        """Save report to file."""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("DATABASE QUALITY CONTROL REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\nTotal Records: {self.stats['total_records']}\n")
            f.write(f"Valid Records: {self.stats['valid_records']}\n")
            f.write(f"Records with Issues: {self.stats['invalid_records']}\n")
            
            if self.stats['invalid_records'] > 0:
                f.write(f"\nIssues by Type:\n")
                for issue_type, count in sorted(self.stats['issues_by_type'].items()):
                    f.write(f"  - {issue_type}: {count}\n")
            
            if self.issues:
                f.write(f"\n{'=' * 80}\n")
                f.write("DETAILED ISSUES\n")
                f.write("=" * 80 + "\n")
                
                for issue in self.issues:
                    f.write(f"ID {issue['id']:5d} | {issue['name'][:40]:40s} | "
                           f"[{issue['type']}] {issue['message']}\n")
        
        print(f"\nReport saved to: {filename}")


def validate_date(year: int, month: int, day: int) -> Tuple[bool, Optional[str]]:
    """Validate a date. Returns (is_valid, error_message)."""
    # Allow historical figures (expanded range for famous people)
    if not (500 <= year <= 2100):
        return False, f"Year {year} is out of valid range (500-2100)"
    
    if not (1 <= month <= 12):
        return False, f"Month {month} is invalid (must be 1-12)"
    
    if not (1 <= day <= 31):
        return False, f"Day {day} is invalid (must be 1-31)"
    
    try:
        # Check if date is valid (handles leap years, etc.)
        calendar.monthrange(year, month)
        datetime(year, month, day)
        return True, None
    except ValueError as e:
        return False, f"Invalid date: {str(e)}"


def validate_time(hour: Optional[int], minute: Optional[int]) -> Tuple[bool, Optional[str]]:
    """Validate time values."""
    if hour is not None:
        if not (0 <= hour <= 23):
            return False, f"Hour {hour} is invalid (must be 0-23)"
    
    if minute is not None:
        if not (0 <= minute <= 59):
            return False, f"Minute {minute} is invalid (must be 0-59)"
    
    return True, None


def validate_chart_data_json(chart_data_json: Optional[str]) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """Validate chart_data_json. Returns (is_valid, error_message, parsed_data)."""
    if not chart_data_json:
        return False, "chart_data_json is missing", None
    
    try:
        data = json.loads(chart_data_json)
        if not isinstance(data, dict):
            return False, "chart_data_json is not a valid JSON object", None
        return True, None, data
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {str(e)}", None


def check_record(record: FamousPerson, report: QualityControlReport):
    """Check a single record for quality issues."""
    report.stats["total_records"] += 1
    has_issues = False
    
    # 1. Required fields
    if not record.name or not record.name.strip():
        report.add_issue(record.id, "N/A", "MISSING_NAME", "Name is missing or empty")
        has_issues = True
    
    if not record.birth_year:
        report.add_issue(record.id, record.name or "N/A", "MISSING_BIRTH_YEAR", "birth_year is missing")
        has_issues = True
    
    if not record.birth_month:
        report.add_issue(record.id, record.name or "N/A", "MISSING_BIRTH_MONTH", "birth_month is missing")
        has_issues = True
    
    if not record.birth_day:
        report.add_issue(record.id, record.name or "N/A", "MISSING_BIRTH_DAY", "birth_day is missing")
        has_issues = True
    
    if not record.birth_location or not record.birth_location.strip():
        report.add_issue(record.id, record.name or "N/A", "MISSING_BIRTH_LOCATION", "birth_location is missing or empty")
        has_issues = True
    
    if not record.wikipedia_url or not record.wikipedia_url.strip():
        report.add_issue(record.id, record.name or "N/A", "MISSING_WIKIPEDIA_URL", "wikipedia_url is missing or empty")
        has_issues = True
    
    # 2. Date validation
    if record.birth_year and record.birth_month and record.birth_day:
        is_valid, error = validate_date(record.birth_year, record.birth_month, record.birth_day)
        if not is_valid:
            report.add_issue(record.id, record.name or "N/A", "INVALID_DATE", error)
            has_issues = True
    
    # 3. Time validation
    if record.birth_hour is not None or record.birth_minute is not None:
        is_valid, error = validate_time(record.birth_hour, record.birth_minute)
        if not is_valid:
            report.add_issue(record.id, record.name or "N/A", "INVALID_TIME", error)
            has_issues = True
    
    # 4. unknown_time consistency - Ascendants are stored in chart_data_json, not separate columns
    # (Rising sign columns have been removed to reduce database size)
    else:
        # If unknown_time is False, should have birth time
        if record.birth_hour is None or record.birth_minute is None:
            report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_UNKNOWN_TIME", 
                           "unknown_time=False but birth_hour or birth_minute is missing")
            has_issues = True
    
    # 5. Chart data JSON validation
    is_valid, error, chart_data = validate_chart_data_json(record.chart_data_json)
    if not is_valid:
        report.add_issue(record.id, record.name or "N/A", "INVALID_CHART_DATA", error)
        has_issues = True
    
    # 5b. Check chart_data_json for ascendant data when unknown_time is True
    if record.unknown_time and chart_data:
        sidereal_positions = chart_data.get("sidereal_major_positions", [])
        tropical_positions = chart_data.get("tropical_major_positions", [])
        
        has_ascendant = any(
            p.get("name") in ["Ascendant", "Rising Sign"] 
            for p in sidereal_positions + tropical_positions
        )
        
        if has_ascendant:
            report.add_issue(record.id, record.name or "N/A", "ASCENDANT_WITH_UNKNOWN_TIME", 
                           "unknown_time=True but chart_data_json contains Ascendant data")
            has_issues = True
    
    # 6. Sign validation (rising signs removed - check chart_data_json instead)
    for sign_field, sign_value in [
        ("sun_sign_sidereal", record.sun_sign_sidereal),
        ("sun_sign_tropical", record.sun_sign_tropical),
        ("moon_sign_sidereal", record.moon_sign_sidereal),
        ("moon_sign_tropical", record.moon_sign_tropical),
    ]:
        if sign_value:
            # Check for "N/A" values
            if sign_value.upper() == "N/A" or sign_value == "N/A":
                report.add_issue(record.id, record.name or "N/A", "N_A_VALUE", 
                               f"{sign_field} is 'N/A' (should be calculated)")
                has_issues = True
            elif sign_value not in VALID_SIGNS:
                report.add_issue(record.id, record.name or "N/A", "INVALID_SIGN", 
                               f"{sign_field} has invalid value: {sign_value}")
                has_issues = True
    
    # 7. Numerology validation
    # Check for "N/A" values (should be fixed)
    if record.life_path_number and (record.life_path_number.upper() == "N/A" or record.life_path_number == "N/A"):
        report.add_issue(record.id, record.name or "N/A", "N_A_VALUE", 
                       f"life_path_number is 'N/A' (should be calculated)")
        has_issues = True
    elif record.life_path_number and not is_valid_life_path(record.life_path_number):
        report.add_issue(record.id, record.name or "N/A", "INVALID_LIFE_PATH", 
                       f"life_path_number has invalid value: {record.life_path_number}")
        has_issues = True
    
    if record.day_number and (record.day_number.upper() == "N/A" or record.day_number == "N/A"):
        report.add_issue(record.id, record.name or "N/A", "N_A_VALUE", 
                       f"day_number is 'N/A' (should be calculated)")
        has_issues = True
    elif record.day_number and not is_valid_day_number(record.day_number):
        report.add_issue(record.id, record.name or "N/A", "INVALID_DAY_NUMBER", 
                       f"day_number has invalid value: {record.day_number}")
        has_issues = True
    
    # 8. Chinese zodiac validation
    if record.chinese_zodiac_animal and (record.chinese_zodiac_animal.upper() == "N/A" or record.chinese_zodiac_animal == "N/A"):
        report.add_issue(record.id, record.name or "N/A", "N_A_VALUE", 
                       f"chinese_zodiac_animal is 'N/A' (should be calculated)")
        has_issues = True
    elif record.chinese_zodiac_animal and record.chinese_zodiac_animal not in VALID_CHINESE_ANIMALS:
        report.add_issue(record.id, record.name or "N/A", "INVALID_CHINESE_ANIMAL", 
                       f"chinese_zodiac_animal has invalid value: {record.chinese_zodiac_animal}")
        has_issues = True
    
    
    # 9. Required chart elements completeness
    missing_fields = []
    if not record.sun_sign_sidereal:
        missing_fields.append("sun_sign_sidereal")
    if not record.sun_sign_tropical:
        missing_fields.append("sun_sign_tropical")
    if not record.moon_sign_sidereal:
        missing_fields.append("moon_sign_sidereal")
    if not record.moon_sign_tropical:
        missing_fields.append("moon_sign_tropical")
    
    if missing_fields:
        if not record.sun_sign_sidereal and not record.sun_sign_tropical:
            report.add_issue(record.id, record.name or "N/A", "MISSING_CHART_DATA", 
                           f"Missing critical chart data: {', '.join(missing_fields)}")
            has_issues = True
        elif len(missing_fields) > 2:  # More than just rising signs missing
            report.add_issue(record.id, record.name or "N/A", "INCOMPLETE_CHART_DATA", 
                           f"Missing chart fields: {', '.join(missing_fields)}")
            has_issues = True
    
    # Check numerology completeness
    if not record.life_path_number:
        report.add_issue(record.id, record.name or "N/A", "MISSING_NUMEROLOGY", 
                       "Missing life_path_number")
        has_issues = True
    if not record.day_number:
        report.add_issue(record.id, record.name or "N/A", "MISSING_NUMEROLOGY", 
                       "Missing day_number")
        has_issues = True
    
    # Check Chinese zodiac completeness
    if not record.chinese_zodiac_animal:
        report.add_issue(record.id, record.name or "N/A", "MISSING_CHINESE_ZODIAC", 
                       "Missing chinese_zodiac_animal")
        has_issues = True
    
    # Check chart_data_json completeness
    if chart_data:
        required_sections = [
            "sidereal_major_positions",
            "tropical_major_positions",
            "numerology_analysis",  # Note: it's "numerology_analysis", not "numerology"
            "chinese_zodiac"
        ]
        missing_sections = []
        for section in required_sections:
            if section not in chart_data or not chart_data[section]:
                missing_sections.append(section)
        
        if missing_sections:
            report.add_issue(record.id, record.name or "N/A", "INCOMPLETE_CHART_JSON", 
                           f"chart_data_json missing sections: {', '.join(missing_sections)}")
            has_issues = True
    
    # 10. Chart data consistency (if chart_data_json is valid, check if signs match)
    if chart_data and not has_issues:
        # Check if extracted signs match chart_data_json
        sidereal_positions = chart_data.get("sidereal_major_positions", [])
        tropical_positions = chart_data.get("tropical_major_positions", [])
        
        # Find sun signs in chart data
        sidereal_sun = next((p for p in sidereal_positions if p.get("name") == "Sun"), None)
        tropical_sun = next((p for p in tropical_positions if p.get("name") == "Sun"), None)
        
        if sidereal_sun:
            sign_str = sidereal_sun.get("sign", "")
            if sign_str:
                sign_parts = sign_str.split()
                if sign_parts:
                    chart_sign = sign_parts[0]  # Get sign name from "Aries 15°30'"
                    if record.sun_sign_sidereal and chart_sign != record.sun_sign_sidereal:
                        report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_CHART_DATA", 
                                       f"sun_sign_sidereal mismatch: DB={record.sun_sign_sidereal}, Chart={chart_sign}")
                        has_issues = True
        
        if tropical_sun:
            sign_str = tropical_sun.get("sign", "")
            if sign_str:
                sign_parts = sign_str.split()
                if sign_parts:
                    chart_sign = sign_parts[0]
                    if record.sun_sign_tropical and chart_sign != record.sun_sign_tropical:
                        report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_CHART_DATA", 
                                       f"sun_sign_tropical mismatch: DB={record.sun_sign_tropical}, Chart={chart_sign}")
                        has_issues = True
    
    # 11. Data structure consistency checks
    # Check if chart_data_json structure is consistent
    if chart_data:
        # Check for expected top-level keys
        expected_keys = ["sidereal_major_positions", "tropical_major_positions", "numerology_analysis", "chinese_zodiac"]
        missing_keys = [key for key in expected_keys if key not in chart_data]
        if missing_keys:
            report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_STRUCTURE", 
                           f"chart_data_json missing expected keys: {', '.join(missing_keys)}")
            has_issues = True
        
        # Check numerology structure (it's stored as "numerology_analysis")
        numerology = chart_data.get("numerology_analysis", {})
        if isinstance(numerology, dict):
            if "life_path_number" not in numerology or not numerology.get("life_path_number"):
                report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_STRUCTURE", 
                               "chart_data_json.numerology_analysis missing life_path_number")
                has_issues = True
        
        # Check Chinese zodiac structure
        chinese_zodiac = chart_data.get("chinese_zodiac", "")
        if not chinese_zodiac or chinese_zodiac == "N/A":
            report.add_issue(record.id, record.name or "N/A", "INCONSISTENT_STRUCTURE", 
                           "chart_data_json.chinese_zodiac is missing or N/A")
            has_issues = True
    
    if not has_issues:
        report.stats["valid_records"] += 1


def check_duplicates(db, report: QualityControlReport):
    """Check for duplicate names."""
    from sqlalchemy import func
    
    duplicates = db.query(
        FamousPerson.name,
        func.count(FamousPerson.id).label('count')
    ).group_by(FamousPerson.name).having(func.count(FamousPerson.id) > 1).all()
    
    if duplicates:
        for name, count in duplicates:
            # Get all IDs with this name
            ids = [r.id for r in db.query(FamousPerson.id).filter(FamousPerson.name == name).all()]
            report.add_issue(ids[0], name, "DUPLICATE_NAME", 
                           f"Found {count} records with same name (IDs: {', '.join(map(str, ids))})")


def main():
    """Main quality control function."""
    print("Initializing database connection...")
    init_db()
    db = SessionLocal()
    
    try:
        report = QualityControlReport()
        
        print("Fetching all records...")
        all_records = db.query(FamousPerson).all()
        
        print(f"Found {len(all_records)} records. Starting quality control checks...")
        print()
        
        # Check each record
        for i, record in enumerate(all_records, 1):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(all_records)} records...")
            check_record(record, report)
        
        # Check for duplicates
        print("\nChecking for duplicate names...")
        check_duplicates(db, report)
        
        # Generate report
        print("\nGenerating report...")
        report.print_report()
        report.save_report("qc_report.txt")
        
        # Summary
        print(f"\n{'=' * 80}")
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Records: {report.stats['total_records']}")
        print(f"Valid Records: {report.stats['valid_records']} ({report.stats['valid_records']/max(report.stats['total_records'],1)*100:.1f}%)")
        print(f"Records with Issues: {report.stats['invalid_records']} ({report.stats['invalid_records']/max(report.stats['total_records'],1)*100:.1f}%)")
        
        if report.stats['invalid_records'] > 0:
            print(f"\n⚠️  Found {report.stats['invalid_records']} records with issues.")
            print("   Review qc_report.txt for details.")
        else:
            print("\n✓ All records passed quality control!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

