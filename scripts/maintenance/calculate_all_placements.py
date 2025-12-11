"""Calculate and store all planetary placements and top 3 aspects for famous people"""

import os
import sys
import json
from typing import Dict, Optional, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson, init_db
from natal_chart import NatalChart, calculate_numerology, get_chinese_zodiac_and_element
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_placements_from_chart_data(chart_data: Dict, unknown_time: bool) -> Dict:
    """Extract all planetary placements from chart data."""
    placements = {
        "sidereal": {},
        "tropical": {}
    }
    
    # Major planets to extract
    major_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Chiron"]
    
    # Extract sidereal placements
    sidereal_positions = chart_data.get("sidereal_major_positions", [])
    for pos in sidereal_positions:
        name = pos.get("name", "")
        if name in major_planets:
            # Extract sign from position string (e.g., "25°30' Capricorn" -> "Capricorn")
            position_str = pos.get("position", "")
            sign = position_str.split()[-1] if position_str else None
            if sign:
                placements["sidereal"][name] = {
                    "sign": sign,
                    "degree": pos.get("degrees"),
                    "retrograde": pos.get("retrograde", False)
                }
    
    # Extract tropical placements
    tropical_positions = chart_data.get("tropical_major_positions", [])
    for pos in tropical_positions:
        name = pos.get("name", "")
        if name in major_planets:
            position_str = pos.get("position", "")
            sign = position_str.split()[-1] if position_str else None
            if sign:
                placements["tropical"][name] = {
                    "sign": sign,
                    "degree": pos.get("degrees"),
                    "retrograde": pos.get("retrograde", False)
                }
    
    # Add Ascendant if time is known
    if not unknown_time:
        for pos in sidereal_positions:
            if pos.get("name") == "Ascendant":
                position_str = pos.get("position", "")
                sign = position_str.split()[-1] if position_str else None
                if sign:
                    placements["sidereal"]["Ascendant"] = {
                        "sign": sign,
                        "degree": pos.get("degrees"),
                        "retrograde": False
                    }
        
        for pos in tropical_positions:
            if pos.get("name") == "Ascendant":
                position_str = pos.get("position", "")
                sign = position_str.split()[-1] if position_str else None
                if sign:
                    placements["tropical"]["Ascendant"] = {
                        "sign": sign,
                        "degree": pos.get("degrees"),
                        "retrograde": False
                    }
    
    return placements

def extract_top_aspects(chart_data: Dict, top_n: int = 3) -> Dict:
    """Extract top N aspects (by strength) for both sidereal and tropical."""
    aspects = {
        "sidereal": [],
        "tropical": []
    }
    
    # Get sidereal aspects
    sidereal_aspects = chart_data.get("sidereal_aspects", [])
    # Sort by strength (score) descending, then by orb ascending
    sorted_sidereal = sorted(
        sidereal_aspects,
        key=lambda a: (
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").isdigit() else 0,
            abs(float(str(a.get("orb", "999")).replace("°", "").strip()) if isinstance(a.get("orb"), str) else float(a.get("orb", 999)))
        )
    )[:top_n]
    
    for aspect in sorted_sidereal:
        # Extract planet names from p1_name and p2_name (e.g., "Sun in Capricorn" -> "Sun")
        p1_name = aspect.get("p1_name", "").split(" in ")[0].strip()
        p2_name = aspect.get("p2_name", "").split(" in ")[0].strip()
        
        aspects["sidereal"].append({
            "p1": p1_name,
            "p2": p2_name,
            "type": aspect.get("type", ""),
            "orb": aspect.get("orb", ""),
            "strength": aspect.get("score", "")
        })
    
    # Get tropical aspects
    tropical_aspects = chart_data.get("tropical_aspects", [])
    sorted_tropical = sorted(
        tropical_aspects,
        key=lambda a: (
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").isdigit() else 0,
            abs(float(str(a.get("orb", "999")).replace("°", "").strip()) if isinstance(a.get("orb"), str) else float(a.get("orb", 999)))
        )
    )[:top_n]
    
    for aspect in sorted_tropical:
        p1_name = aspect.get("p1_name", "").split(" in ")[0].strip()
        p2_name = aspect.get("p2_name", "").split(" in ")[0].strip()
        
        aspects["tropical"].append({
            "p1": p1_name,
            "p2": p2_name,
            "type": aspect.get("type", ""),
            "orb": aspect.get("orb", ""),
            "strength": aspect.get("score", "")
        })
    
    return aspects

def calculate_placements_for_person(person: FamousPerson) -> bool:
    """Calculate and store placements and aspects for a person."""
    try:
        # Check if we have the necessary data
        if not all([person.birth_year, person.birth_month, person.birth_day, person.birth_location]):
            logger.warning(f"Skipping {person.name}: Missing birth data")
            return False
        
        # Parse location from chart_data_json if available, or use birth_location
        lat, lng, timezone = None, None, None
        unknown_time = person.unknown_time if person.unknown_time is not None else True
        
        # Try to get coordinates from chart_data_json
        if person.chart_data_json:
            try:
                chart_data = json.loads(person.chart_data_json)
                # Extract placements and aspects from existing chart data
                placements = extract_placements_from_chart_data(chart_data, unknown_time)
                top_aspects = extract_top_aspects(chart_data, top_n=3)
                
                # Store in database (only JSON, no individual columns)
                person.planetary_placements_json = json.dumps(placements)
                person.top_aspects_json = json.dumps(top_aspects)
                
                return True
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON for {person.name}, will recalculate")
        
        # If chart_data_json doesn't exist or is invalid, we need to recalculate
        # This requires geocoding, which we'll skip for now if we don't have coordinates
        logger.warning(f"Cannot recalculate {person.name}: Need geocoding data")
        return False
        
    except Exception as e:
        logger.error(f"Error processing {person.name}: {e}")
        return False

def update_all_placements(update_existing: bool = False):
    """Update placements and aspects for all people in the database."""
    db = SessionLocal()
    
    try:
        if update_existing:
            all_people = db.query(FamousPerson).all()
            print("Updating placements for ALL records...")
            logger.info("Updating placements for ALL records...")
        else:
            all_people = db.query(FamousPerson).filter(
                (FamousPerson.planetary_placements_json.is_(None)) |
                (FamousPerson.top_aspects_json.is_(None))
            ).all()
            print("Updating placements for records with missing data...")
            logger.info("Updating placements for records with missing data...")
        
        total = len(all_people)
        print(f"Processing {total} records...")
        logger.info(f"Processing {total} records...")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, person in enumerate(all_people, 1):
            if idx % 100 == 0 or idx <= 10:
                print(f"[{idx}/{total}] Processing {person.name}...")
            logger.info(f"[{idx}/{total}] Processing {person.name}...")
            
            if calculate_placements_for_person(person):
                updated_count += 1
            else:
                skipped_count += 1
            
            # Commit every 10 records
            if updated_count % 10 == 0 and updated_count > 0:
                db.commit()
                if updated_count % 100 == 0:
                    print(f"  Progress: {updated_count} updated, {skipped_count} skipped")
                logger.info(f"  Progress: {updated_count} updated, {skipped_count} skipped")
        
        # Final commit
        db.commit()
        
        print("=" * 60)
        print("UPDATE COMPLETE")
        print(f"Total records: {total}")
        print(f"Successfully updated: {updated_count}")
        print(f"Skipped: {skipped_count}")
        print(f"Errors: {error_count}")
        print("=" * 60)
        
        logger.info("=" * 60)
        logger.info("UPDATE COMPLETE")
        logger.info(f"Total records: {total}")
        logger.info(f"Successfully updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error updating placements: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Calculate and store all placements and aspects")
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update all records, even if they already have data"
    )
    args = parser.parse_args()
    
    update_all_placements(update_existing=args.update_all)

