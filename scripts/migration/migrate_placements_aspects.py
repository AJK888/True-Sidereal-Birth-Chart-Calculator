"""
Migration script to add and populate planetary placements and aspects data.

This script:
1. Adds planetary_placements_json and top_aspects_json columns to saved_charts table
2. Extracts and populates placement/aspect data for all saved_charts records
3. Populates missing placement/aspect data for famous_people records

Usage:
    python scripts/migration/migrate_placements_aspects.py [--update-all] [--saved-charts-only] [--famous-people-only]
"""

import os
import sys
import json
import logging
from typing import Dict, Optional, List
from sqlalchemy import text, inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database import SessionLocal, SavedChart, FamousPerson, init_db, engine
# Note: We don't need NatalChart here - we're extracting from existing chart_data_json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
                    "retrograde": pos.get("retrograde", False),
                    "house": pos.get("house_num") if not unknown_time else None
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
                    "retrograde": pos.get("retrograde", False),
                    "house": pos.get("house_num") if not unknown_time else None
                }
    
    # Add Ascendant if time is known
    if not unknown_time:
        sidereal_additional = chart_data.get("sidereal_additional_points", [])
        tropical_additional = chart_data.get("tropical_additional_points", [])
        
        for pos in sidereal_additional:
            if pos.get("name") == "Ascendant":
                info_str = pos.get("info", "")
                sign = info_str.split()[0] if info_str else None
                if sign:
                    # Try to extract degree from position string
                    position_str = info_str.split("–")[0].strip() if "–" in info_str else info_str
                    degree = None
                    if "°" in position_str:
                        try:
                            degree = float(position_str.split("°")[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    placements["sidereal"]["Ascendant"] = {
                        "sign": sign,
                        "degree": degree,
                        "retrograde": False
                    }
                break
        
        for pos in tropical_additional:
            if pos.get("name") == "Ascendant":
                info_str = pos.get("info", "")
                sign = info_str.split()[0] if info_str else None
                if sign:
                    position_str = info_str.split("–")[0].strip() if "–" in info_str else info_str
                    degree = None
                    if "°" in position_str:
                        try:
                            degree = float(position_str.split("°")[0].strip())
                        except (ValueError, IndexError):
                            pass
                    
                    placements["tropical"]["Ascendant"] = {
                        "sign": sign,
                        "degree": degree,
                        "retrograde": False
                    }
                break
    
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
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").replace("-", "").isdigit() else 0,
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
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").replace("-", "").isdigit() else 0,
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


def add_columns_to_saved_charts():
    """Add planetary_placements_json and top_aspects_json columns to saved_charts table if they don't exist."""
    db = SessionLocal()
    
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('saved_charts')]
        
        with engine.connect() as conn:
            if 'planetary_placements_json' not in columns:
                logger.info("Adding planetary_placements_json column to saved_charts...")
                conn.execute(text("ALTER TABLE saved_charts ADD COLUMN planetary_placements_json TEXT"))
                conn.commit()
                logger.info("✓ Added planetary_placements_json column")
            else:
                logger.info("✓ planetary_placements_json column already exists")
            
            if 'top_aspects_json' not in columns:
                logger.info("Adding top_aspects_json column to saved_charts...")
                conn.execute(text("ALTER TABLE saved_charts ADD COLUMN top_aspects_json TEXT"))
                conn.commit()
                logger.info("✓ Added top_aspects_json column")
            else:
                logger.info("✓ top_aspects_json column already exists")
        
        logger.info("Column migration complete!")
        
    except Exception as e:
        logger.error(f"Error adding columns: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def populate_saved_charts(update_existing: bool = False):
    """Populate placement and aspect data for saved_charts."""
    db = SessionLocal()
    
    try:
        if update_existing:
            all_charts = db.query(SavedChart).filter(SavedChart.chart_data_json.isnot(None)).all()
            logger.info("Updating placements for ALL saved_charts records...")
        else:
            all_charts = db.query(SavedChart).filter(
                SavedChart.chart_data_json.isnot(None),
                (
                    (SavedChart.planetary_placements_json.is_(None)) |
                    (SavedChart.top_aspects_json.is_(None))
                )
            ).all()
            logger.info("Updating placements for saved_charts with missing data...")
        
        total = len(all_charts)
        logger.info(f"Processing {total} saved_charts records...")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, chart in enumerate(all_charts, 1):
            if idx % 100 == 0 or idx <= 10:
                logger.info(f"[{idx}/{total}] Processing chart {chart.id} ({chart.chart_name})...")
            
            try:
                if not chart.chart_data_json:
                    skipped_count += 1
                    continue
                
                chart_data = json.loads(chart.chart_data_json)
                unknown_time = chart.unknown_time if chart.unknown_time is not None else False
                
                # Extract placements and aspects
                placements = extract_placements_from_chart_data(chart_data, unknown_time)
                top_aspects = extract_top_aspects(chart_data, top_n=3)
                
                # Store in database
                chart.planetary_placements_json = json.dumps(placements)
                chart.top_aspects_json = json.dumps(top_aspects)
                
                updated_count += 1
                
                # Commit every 10 records
                if updated_count % 10 == 0:
                    db.commit()
                    if updated_count % 100 == 0:
                        logger.info(f"  Progress: {updated_count} updated, {skipped_count} skipped, {error_count} errors")
                
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON for chart {chart.id}: {e}")
                error_count += 1
            except Exception as e:
                logger.error(f"Error processing chart {chart.id}: {e}")
                error_count += 1
        
        # Final commit
        db.commit()
        
        logger.info("=" * 60)
        logger.info("SAVED CHARTS MIGRATION COMPLETE")
        logger.info(f"Total records: {total}")
        logger.info(f"Successfully updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error updating saved_charts: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def populate_famous_people(update_existing: bool = False):
    """Populate missing placement and aspect data for famous_people."""
    db = SessionLocal()
    
    try:
        if update_existing:
            all_people = db.query(FamousPerson).filter(FamousPerson.chart_data_json.isnot(None)).all()
            logger.info("Updating placements for ALL famous_people records...")
        else:
            all_people = db.query(FamousPerson).filter(
                FamousPerson.chart_data_json.isnot(None),
                (
                    (FamousPerson.planetary_placements_json.is_(None)) |
                    (FamousPerson.top_aspects_json.is_(None))
                )
            ).all()
            logger.info("Updating placements for famous_people with missing data...")
        
        total = len(all_people)
        logger.info(f"Processing {total} famous_people records...")
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for idx, person in enumerate(all_people, 1):
            if idx % 100 == 0 or idx <= 10:
                logger.info(f"[{idx}/{total}] Processing {person.name}...")
            
            try:
                if not person.chart_data_json:
                    skipped_count += 1
                    continue
                
                chart_data = json.loads(person.chart_data_json)
                unknown_time = person.unknown_time if person.unknown_time is not None else True
                
                # Extract placements and aspects
                placements = extract_placements_from_chart_data(chart_data, unknown_time)
                top_aspects = extract_top_aspects(chart_data, top_n=3)
                
                # Store in database
                person.planetary_placements_json = json.dumps(placements)
                person.top_aspects_json = json.dumps(top_aspects)
                
                updated_count += 1
                
                # Commit every 10 records
                if updated_count % 10 == 0:
                    db.commit()
                    if updated_count % 100 == 0:
                        logger.info(f"  Progress: {updated_count} updated, {skipped_count} skipped, {error_count} errors")
                
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON for {person.name}: {e}")
                error_count += 1
            except Exception as e:
                logger.error(f"Error processing {person.name}: {e}")
                error_count += 1
        
        # Final commit
        db.commit()
        
        logger.info("=" * 60)
        logger.info("FAMOUS PEOPLE MIGRATION COMPLETE")
        logger.info(f"Total records: {total}")
        logger.info(f"Successfully updated: {updated_count}")
        logger.info(f"Skipped: {skipped_count}")
        logger.info(f"Errors: {error_count}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error updating famous_people: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def main():
    """Main migration function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate placement and aspect data to database")
    parser.add_argument(
        "--update-all",
        action="store_true",
        help="Update all records, even if they already have data"
    )
    parser.add_argument(
        "--saved-charts-only",
        action="store_true",
        help="Only migrate saved_charts table"
    )
    parser.add_argument(
        "--famous-people-only",
        action="store_true",
        help="Only migrate famous_people table"
    )
    parser.add_argument(
        "--columns-only",
        action="store_true",
        help="Only add columns, don't populate data"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("PLACEMENT & ASPECT DATA MIGRATION")
    logger.info("=" * 60)
    
    # Step 1: Add columns to saved_charts
    if not args.famous_people_only:
        logger.info("\n[STEP 1] Adding columns to saved_charts table...")
        add_columns_to_saved_charts()
    
    # Step 2: Populate data
    if not args.columns_only:
        if not args.famous_people_only:
            logger.info("\n[STEP 2] Populating saved_charts data...")
            populate_saved_charts(update_existing=args.update_all)
        
        if not args.saved_charts_only:
            logger.info("\n[STEP 3] Populating famous_people data...")
            populate_famous_people(update_existing=args.update_all)
    
    logger.info("\n" + "=" * 60)
    logger.info("MIGRATION COMPLETE!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
