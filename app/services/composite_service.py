"""
Composite Chart Service

Calculates composite charts - a midpoint-based chart representing the relationship
between two people as a single entity.
"""

import logging
from typing import Dict, List, Any, Optional
from natal_chart import NatalChart, CelestialBody, ASPECTS_CONFIG, ASPECT_SCORES
import math

logger = logging.getLogger(__name__)


def calculate_midpoint(pos1: float, pos2: float) -> float:
    """
    Calculate the midpoint between two positions.
    
    Args:
        pos1: First position in degrees (0-360)
        pos2: Second position in degrees (0-360)
    
    Returns:
        Midpoint position in degrees (0-360)
    """
    # Handle wrap-around
    diff = abs(pos1 - pos2)
    if diff > 180:
        # Positions are on opposite sides of the circle
        # Add 360 to the smaller one
        if pos1 < pos2:
            pos1 += 360
        else:
            pos2 += 360
    
    midpoint = (pos1 + pos2) / 2.0
    return midpoint % 360


def calculate_composite_planets(
    chart1_bodies: List[CelestialBody],
    chart2_bodies: List[CelestialBody],
    system: str = "sidereal"
) -> List[Dict[str, Any]]:
    """
    Calculate composite planet positions (midpoints).
    
    Args:
        chart1_bodies: List of celestial bodies from first chart
        chart2_bodies: List of celestial bodies from second chart
        system: "sidereal" or "tropical"
    
    Returns:
        List of composite planet dictionaries
    """
    composite_planets = []
    
    # Create lookup dictionaries
    chart1_lookup = {body.name: body for body in chart1_bodies}
    chart2_lookup = {body.name: body for body in chart2_bodies}
    
    # Calculate midpoints for each planet
    planet_names = ["Sun", "Moon", "Mercury", "Venus", "Mars", 
                   "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    
    for planet_name in planet_names:
        if planet_name in chart1_lookup and planet_name in chart2_lookup:
            body1 = chart1_lookup[planet_name]
            body2 = chart2_lookup[planet_name]
            
            pos1 = body1.sidereal_longitude if system == "sidereal" else body1.tropical_longitude
            pos2 = body2.sidereal_longitude if system == "sidereal" else body2.tropical_longitude
            
            composite_pos = calculate_midpoint(pos1, pos2)
            
            # Determine if composite planet is retrograde (if both are retrograde)
            is_retro = body1.is_retrograde and body2.is_retrograde
            
            composite_planets.append({
                "name": planet_name,
                "position": round(composite_pos, 4),
                "is_retrograde": is_retro,
                "chart1_position": round(pos1, 4),
                "chart2_position": round(pos2, 4)
            })
    
    return composite_planets


def calculate_composite_ascendant(
    chart1: NatalChart,
    chart2: NatalChart,
    system: str = "sidereal"
) -> float:
    """
    Calculate composite ascendant (midpoint of the two ascendants).
    
    Args:
        chart1: First birth chart
        chart2: Second birth chart
        system: "sidereal" or "tropical"
    
    Returns:
        Composite ascendant position in degrees
    """
    if system == "sidereal":
        asc1 = chart1.ascendant_data.get("sidereal_asc", 0)
        asc2 = chart2.ascendant_data.get("sidereal_asc", 0)
    else:
        asc1 = chart1.ascendant_data.get("tropical_asc", 0)
        asc2 = chart2.ascendant_data.get("tropical_asc", 0)
    
    return calculate_midpoint(asc1, asc2)


def calculate_composite_aspects(
    composite_planets: List[Dict[str, Any]],
    composite_asc: float
) -> List[Dict[str, Any]]:
    """
    Calculate aspects in the composite chart.
    
    Args:
        composite_planets: List of composite planet positions
        composite_asc: Composite ascendant position
    
    Returns:
        List of aspect dictionaries
    """
    aspects = []
    
    # Add ascendant to the list for aspect calculations
    all_points = composite_planets + [{"name": "Ascendant", "position": composite_asc}]
    
    # Calculate aspects between all points
    for i, p1 in enumerate(all_points):
        for p2 in all_points[i+1:]:
            if p1["name"] == p2["name"]:
                continue
            
            pos1 = p1["position"]
            pos2 = p2["position"]
            
            # Calculate angular distance
            angular_distance = abs(pos1 - pos2)
            if angular_distance > 180:
                angular_distance = 360 - angular_distance
            
            # Check for aspects
            for aspect_name, aspect_angle, orb in ASPECTS_CONFIG:
                if abs(angular_distance - aspect_angle) <= orb:
                    exact_orb = abs(angular_distance - aspect_angle)
                    strength = 1.0 - (exact_orb / orb)
                    
                    aspects.append({
                        "planet1": p1["name"],
                        "planet2": p2["name"],
                        "aspect": aspect_name,
                        "angle": aspect_angle,
                        "orb": round(exact_orb, 2),
                        "strength": round(strength, 3),
                        "score": ASPECT_SCORES.get(aspect_name, 1.0)
                    })
    
    # Sort by score
    aspects.sort(key=lambda x: x["score"], reverse=True)
    
    return aspects


def calculate_composite(
    chart1: NatalChart,
    chart2: NatalChart,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate complete composite chart.
    
    Args:
        chart1: First birth chart
        chart2: Second birth chart
        system: "sidereal" or "tropical"
    
    Returns:
        Complete composite chart analysis dictionary
    """
    try:
        # Get chart bodies
        chart1_bodies = chart1.celestial_bodies if system == "sidereal" else chart1.tropical_bodies
        chart2_bodies = chart2.celestial_bodies if system == "sidereal" else chart2.tropical_bodies
        
        # Calculate composite planets
        composite_planets = calculate_composite_planets(chart1_bodies, chart2_bodies, system)
        
        # Calculate composite ascendant
        composite_asc = calculate_composite_ascendant(chart1, chart2, system)
        
        # Calculate composite aspects
        composite_aspects = calculate_composite_aspects(composite_planets, composite_asc)
        
        # Get top aspects
        top_aspects = composite_aspects[:15]
        
        # Organize aspects by type
        aspects_by_type = {}
        for aspect in composite_aspects:
            aspect_type = aspect["aspect"]
            if aspect_type not in aspects_by_type:
                aspects_by_type[aspect_type] = []
            aspects_by_type[aspect_type].append(aspect)
        
        return {
            "chart1_name": chart1.name,
            "chart2_name": chart2.name,
            "system": system,
            "composite_ascendant": round(composite_asc, 4),
            "planets": composite_planets,
            "aspects": {
                "all": composite_aspects,
                "top": top_aspects,
                "by_type": aspects_by_type,
                "count": len(composite_aspects)
            },
            "summary": {
                "total_aspects": len(composite_aspects),
                "key_aspects": [a for a in top_aspects[:5]],
                "description": "Composite chart represents the relationship as a single entity"
            }
        }
    
    except Exception as e:
        logger.error(f"Error calculating composite chart: {e}", exc_info=True)
        raise

