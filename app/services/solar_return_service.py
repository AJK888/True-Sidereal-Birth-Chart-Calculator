"""
Solar Return Service

Calculates solar return charts - charts for when the Sun returns to its natal position.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from natal_chart import NatalChart
import swisseph as swe

logger = logging.getLogger(__name__)


def find_solar_return_date(
    natal_chart: NatalChart,
    target_year: int,
    system: str = "sidereal"
) -> datetime:
    """
    Find the date when the Sun returns to its natal position.
    
    Args:
        natal_chart: The natal birth chart
        target_year: Year to find solar return for
        system: "sidereal" or "tropical"
    
    Returns:
        Datetime of solar return
    """
    # Get natal Sun position
    natal_sun = next(
        (b for b in (natal_chart.celestial_bodies if system == "sidereal" else natal_chart.tropical_bodies)
         if b.name == "Sun"),
        None
    )
    
    if not natal_sun:
        raise ValueError("Natal Sun position not found")
    
    natal_sun_pos = natal_sun.sidereal_longitude if system == "sidereal" else natal_sun.tropical_longitude
    
    # Start searching from birthday in target year
    start_date = datetime(target_year, natal_chart.birth_month, natal_chart.birth_day, 12, 0)
    
    # Search within ±30 days of birthday
    search_range = 30
    best_date = start_date
    min_diff = 360.0
    
    ayanamsa = natal_chart.ascendant_data.get("ayanamsa", 0)
    
    for day_offset in range(-search_range, search_range + 1):
        test_date = start_date + timedelta(days=day_offset)
        jd = swe.julday(
            test_date.year,
            test_date.month,
            test_date.day,
            test_date.hour + test_date.minute / 60.0
        )
        
        try:
            res = swe.calc_ut(jd, swe.SUN)
            if system == "sidereal":
                sun_pos = (res[0][0] - ayanamsa + 360) % 360
            else:
                sun_pos = res[0][0] % 360
            
            # Calculate difference (handle wrap-around)
            diff = abs(sun_pos - natal_sun_pos)
            if diff > 180:
                diff = 360 - diff
            
            if diff < min_diff:
                min_diff = diff
                best_date = test_date
        except Exception:
            continue
    
    return best_date


def calculate_solar_return_chart(
    natal_chart: NatalChart,
    target_year: int,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate solar return chart for a target year.
    
    Args:
        natal_chart: The natal birth chart
        target_year: Year to calculate solar return for
        system: "sidereal" or "tropical"
    
    Returns:
        Dictionary with solar return chart information
    """
    try:
        # Find solar return date
        solar_return_date = find_solar_return_date(natal_chart, target_year, system)
        
        # Calculate chart for solar return date
        # Use natal location for solar return
        solar_return_chart = NatalChart(
            name=f"{natal_chart.name} Solar Return {target_year}",
            year=solar_return_date.year,
            month=solar_return_date.month,
            day=solar_return_date.day,
            hour=solar_return_date.hour,
            minute=solar_return_date.minute,
            latitude=natal_chart.latitude,
            longitude=natal_chart.longitude
        )
        solar_return_chart.calculate_chart(unknown_time=False)
        
        # Get solar return planets
        solar_return_bodies = solar_return_chart.celestial_bodies if system == "sidereal" else solar_return_chart.tropical_bodies
        natal_bodies = natal_chart.celestial_bodies if system == "sidereal" else natal_chart.tropical_bodies
        
        # Compare solar return to natal
        planet_comparisons = []
        for sr_body in solar_return_bodies:
            if sr_body.name not in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                   "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                continue
            
            natal_body = next((b for b in natal_bodies if b.name == sr_body.name), None)
            if not natal_body:
                continue
            
            sr_pos = sr_body.sidereal_longitude if system == "sidereal" else sr_body.tropical_longitude
            natal_pos = natal_body.sidereal_longitude if system == "sidereal" else natal_body.tropical_longitude
            
            # Calculate movement
            movement = (sr_pos - natal_pos) % 360
            if movement > 180:
                movement = movement - 360
            
            planet_comparisons.append({
                "name": sr_body.name,
                "solar_return_position": round(sr_pos, 4),
                "natal_position": round(natal_pos, 4),
                "movement": round(movement, 4),
                "is_retrograde": sr_body.is_retrograde
            })
        
        # Get ascendant comparison
        sr_asc = solar_return_chart.ascendant_data.get(
            "sidereal_asc" if system == "sidereal" else "tropical_asc", 0
        )
        natal_asc = natal_chart.ascendant_data.get(
            "sidereal_asc" if system == "sidereal" else "tropical_asc", 0
        )
        
        return {
            "natal_chart_name": natal_chart.name,
            "solar_return_year": target_year,
            "solar_return_date": solar_return_date.isoformat(),
            "system": system,
            "solar_return_chart": {
                "ascendant": round(sr_asc, 4),
                "natal_ascendant": round(natal_asc, 4),
                "ascendant_movement": round((sr_asc - natal_asc) % 360, 4),
                "planets": planet_comparisons
            },
            "summary": {
                "description": f"Solar return chart for {target_year}",
                "key_changes": [p for p in planet_comparisons if abs(p["movement"]) > 30]
            }
        }
    
    except Exception as e:
        logger.error(f"Error calculating solar return chart: {e}", exc_info=True)
        raise

