"""
Transit Service

Calculates current planetary transits to a natal chart.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from natal_chart import NatalChart, CelestialBody, ASPECTS_CONFIG, ASPECT_SCORES
import swisseph as swe

logger = logging.getLogger(__name__)


def calculate_current_transits(
    natal_chart: NatalChart,
    target_date: Optional[datetime] = None,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate current transits to a natal chart.
    
    Args:
        natal_chart: The natal birth chart
        target_date: Date to calculate transits for (defaults to now)
        system: "sidereal" or "tropical"
    
    Returns:
        Dictionary with transit information
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc)
    
    try:
        # Calculate Julian day for target date
        jd = swe.julday(
            target_date.year,
            target_date.month,
            target_date.day,
            target_date.hour + target_date.minute / 60.0
        )
        
        # Get ayanamsa for sidereal calculations
        ayanamsa = natal_chart.ascendant_data.get("ayanamsa", 0)
        
        # Get natal planets
        natal_bodies = natal_chart.celestial_bodies if system == "sidereal" else natal_chart.tropical_bodies
        
        # Calculate current positions of transiting planets
        transiting_planets = []
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
                    transit_pos = (res[0][0] - ayanamsa + 360) % 360
                else:
                    transit_pos = res[0][0] % 360
                
                transiting_planets.append({
                    "name": name,
                    "position": round(transit_pos, 4),
                    "is_retrograde": is_retro
                })
            except Exception as e:
                logger.warning(f"Failed to calculate transit for {name}: {e}")
                continue
        
        # Calculate aspects between transiting planets and natal planets
        transit_aspects = []
        
        for transit_planet in transiting_planets:
            transit_pos = transit_planet["position"]
            
            for natal_body in natal_bodies:
                if natal_body.name not in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                          "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                    continue
                
                natal_pos = natal_body.sidereal_longitude if system == "sidereal" else natal_body.tropical_longitude
                
                # Calculate angular distance
                angular_distance = abs(transit_pos - natal_pos)
                if angular_distance > 180:
                    angular_distance = 360 - angular_distance
                
                # Check for aspects
                for aspect_name, aspect_angle, orb in ASPECTS_CONFIG:
                    if abs(angular_distance - aspect_angle) <= orb:
                        exact_orb = abs(angular_distance - aspect_angle)
                        strength = 1.0 - (exact_orb / orb)
                        
                        transit_aspects.append({
                            "transiting_planet": transit_planet["name"],
                            "natal_planet": natal_body.name,
                            "aspect": aspect_name,
                            "angle": aspect_angle,
                            "orb": round(exact_orb, 2),
                            "strength": round(strength, 3),
                            "score": ASPECT_SCORES.get(aspect_name, 1.0),
                            "transit_position": round(transit_pos, 4),
                            "natal_position": round(natal_pos, 4)
                        })
        
        # Sort by score (most significant first)
        transit_aspects.sort(key=lambda x: x["score"], reverse=True)
        
        # Get active transits (within orb)
        active_transits = [t for t in transit_aspects if t["orb"] <= 2.0]  # Within 2 degrees
        
        # Organize by transiting planet
        transits_by_planet = {}
        for transit in transit_aspects:
            planet = transit["transiting_planet"]
            if planet not in transits_by_planet:
                transits_by_planet[planet] = []
            transits_by_planet[planet].append(transit)
        
        return {
            "natal_chart_name": natal_chart.name,
            "transit_date": target_date.isoformat(),
            "system": system,
            "transiting_planets": transiting_planets,
            "transit_aspects": {
                "all": transit_aspects,
                "active": active_transits,
                "by_planet": transits_by_planet,
                "count": len(transit_aspects),
                "active_count": len(active_transits)
            },
            "summary": {
                "total_transits": len(transit_aspects),
                "active_transits": len(active_transits),
                "most_significant": [t for t in transit_aspects[:5]]
            }
        }
    
    except Exception as e:
        logger.error(f"Error calculating transits: {e}", exc_info=True)
        raise

