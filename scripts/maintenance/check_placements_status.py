"""Check if famous people have placements and aspects calculated."""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, FamousPerson

def check_placements_status():
    """Check the status of placements and aspects in the database."""
    db = SessionLocal()
    
    try:
        total = db.query(FamousPerson).count()
        has_chart = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None)
        ).count()
        has_placements = db.query(FamousPerson).filter(
            FamousPerson.planetary_placements_json.isnot(None)
        ).count()
        has_aspects = db.query(FamousPerson).filter(
            FamousPerson.top_aspects_json.isnot(None)
        ).count()
        has_both = db.query(FamousPerson).filter(
            FamousPerson.planetary_placements_json.isnot(None),
            FamousPerson.top_aspects_json.isnot(None)
        ).count()
        
        missing_placements = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None),
            FamousPerson.planetary_placements_json.is_(None)
        ).count()
        missing_aspects = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None),
            FamousPerson.top_aspects_json.is_(None)
        ).count()
        
        print("=" * 70)
        print("PLACEMENT AND ASPECT CALCULATION STATUS")
        print("=" * 70)
        print(f"Total records: {total:,}")
        print(f"Records with chart_data_json: {has_chart:,}")
        print(f"Records with planetary_placements_json: {has_placements:,}")
        print(f"Records with top_aspects_json: {has_aspects:,}")
        print(f"Records with BOTH placements AND aspects: {has_both:,}")
        print()
        print("Missing data:")
        print(f"  - Has chart but missing placements: {missing_placements:,}")
        print(f"  - Has chart but missing aspects: {missing_aspects:,}")
        
        # Check a sample record
        if has_both > 0:
            sample = db.query(FamousPerson).filter(
                FamousPerson.planetary_placements_json.isnot(None),
                FamousPerson.top_aspects_json.isnot(None)
            ).first()
            
            if sample:
                placements = json.loads(sample.planetary_placements_json) if sample.planetary_placements_json else {}
                aspects = json.loads(sample.top_aspects_json) if sample.top_aspects_json else {}
                
                print()
                print("=" * 70)
                print("SAMPLE RECORD VERIFICATION")
                print("=" * 70)
                print(f"Name: {sample.name}")
                print(f"Has placements: {bool(placements)}")
                if placements:
                    sidereal_planets = placements.get("sidereal", {})
                    tropical_planets = placements.get("tropical", {})
                    print(f"  Sidereal planets: {len(sidereal_planets)} ({', '.join(list(sidereal_planets.keys())[:5])}...)")
                    print(f"  Tropical planets: {len(tropical_planets)} ({', '.join(list(tropical_planets.keys())[:5])}...)")
                print(f"Has aspects: {bool(aspects)}")
                if aspects:
                    sidereal_aspects = aspects.get("sidereal", [])
                    tropical_aspects = aspects.get("tropical", [])
                    print(f"  Sidereal aspects: {len(sidereal_aspects)}")
                    print(f"  Tropical aspects: {len(tropical_aspects)}")
        
        print("=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    check_placements_status()

