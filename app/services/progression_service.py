"""
Progression Service

Calculates progressed charts - charts that show how a natal chart evolves over time.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from natal_chart import NatalChart
import swisseph as swe

logger = logging.getLogger(__name__)


def calculate_progressed_chart(
    natal_chart: NatalChart,
    target_date: datetime,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate a progressed chart for a target date.
    
    Progressed charts use the "day for a year" method where each day after birth
    represents one year of life.
    
    Args:
        natal_chart: The natal birth chart
        target_date: Date to calculate progressed chart for
        system: "sidereal" or "tropical"
    
    Returns:
        Dictionary with progressed chart information
    """
    try:
        # Calculate days since birth
        birth_date = datetime(
            natal_chart.birth_year,
            natal_chart.birth_month,
            natal_chart.birth_day,
            natal_chart.birth_hour,
            natal_chart.birth_minute
        )
        
        days_since_birth = (target_date - birth_date).days
        progressed_year = natal_chart.birth_year + days_since_birth
        
        # Calculate progressed date (birth date + days_since_birth)
        progressed_date = birth_date + timedelta(days=days_since_birth)
        
        # Calculate Julian day for progressed date
        jd = swe.julday(
            progressed_date.year,
            progressed_date.month,
            progressed_date.day,
            progressed_date.hour + progressed_date.minute / 60.0
        )
        
        # Get ayanamsa
        ayanamsa = natal_chart.ascendant_data.get("ayanamsa", 0)
        
        # Calculate progressed planetary positions
        progressed_planets = []
        planet_config = [
            ("Sun", swe.SUN), ("Moon", swe.MOON), ("Mercury", swe.MERCURY),
            ("Venus", swe.VENUS), ("Mars", swe.MARS), ("Jupiter", swe.JUPITER),
            ("Saturn", swe.SATURN), ("Uranus", swe.URANUS), ("Neptune", swe.NEPTUNE),
            ("Pluto", swe.PLUTO)
        ]
        
        for name, code in planet_config:
            try:
                res = swe.calc_ut(jd, code)
                is_retro = res[0][3] < 0
                
                if system == "sidereal":
                    progressed_pos = (res[0][0] - ayanamsa + 360) % 360
                else:
                    progressed_pos = res[0][0] % 360
                
                # Get natal position for comparison
                natal_body = next(
                    (b for b in (natal_chart.celestial_bodies if system == "sidereal" else natal_chart.tropical_bodies)
                     if b.name == name),
                    None
                )
                natal_pos = natal_body.sidereal_longitude if (natal_body and system == "sidereal") else (
                    natal_body.tropical_longitude if natal_body else None
                )
                
                progressed_planets.append({
                    "name": name,
                    "progressed_position": round(progressed_pos, 4),
                    "natal_position": round(natal_pos, 4) if natal_pos is not None else None,
                    "movement": round((progressed_pos - natal_pos) % 360, 4) if natal_pos is not None else None,
                    "is_retrograde": is_retro
                })
            except Exception as e:
                logger.warning(f"Failed to calculate progressed position for {name}: {e}")
                continue
        
        # Calculate progressed ascendant
        try:
            res = swe.houses(jd, natal_chart.latitude, natal_chart.longitude, b'P')
            if system == "sidereal":
                progressed_asc = (res[1][0] - ayanamsa + 360) % 360
            else:
                progressed_asc = res[1][0] % 360
            
            natal_asc = natal_chart.ascendant_data.get(
                "sidereal_asc" if system == "sidereal" else "tropical_asc", 0
            )
            
            progressed_ascendant = {
                "progressed": round(progressed_asc, 4),
                "natal": round(natal_asc, 4),
                "movement": round((progressed_asc - natal_asc) % 360, 4)
            }
        except Exception as e:
            logger.warning(f"Failed to calculate progressed ascendant: {e}")
            progressed_ascendant = None
        
        return {
            "natal_chart_name": natal_chart.name,
            "progressed_date": progressed_date.isoformat(),
            "progressed_year": progressed_year,
            "days_since_birth": days_since_birth,
            "system": system,
            "progressed_planets": progressed_planets,
            "progressed_ascendant": progressed_ascendant,
            "summary": {
                "age_at_progression": days_since_birth,
                "description": f"Progressed chart for age {days_since_birth} (day-for-year method)"
            }
        }
    
    except Exception as e:
        logger.error(f"Error calculating progressed chart: {e}", exc_info=True)
        raise

