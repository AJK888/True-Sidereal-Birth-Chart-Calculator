"""
Synastry Service

Calculates relationship compatibility between two birth charts by comparing
planetary positions, aspects, and house overlays.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from natal_chart import NatalChart, CelestialBody, Aspect, ASPECTS_CONFIG, ASPECT_SCORES
import math

logger = logging.getLogger(__name__)


def calculate_synastry_aspects(
    chart1_bodies: List[CelestialBody],
    chart2_bodies: List[CelestialBody],
    system: str = "sidereal"
) -> List[Dict[str, Any]]:
    """
    Calculate aspects between planets in two charts.
    
    Args:
        chart1_bodies: List of celestial bodies from first chart
        chart2_bodies: List of celestial bodies from second chart
        system: "sidereal" or "tropical"
    
    Returns:
        List of aspect dictionaries
    """
    aspects = []
    
    # Create lookup dictionaries for faster access
    chart1_lookup = {body.name: body for body in chart1_bodies}
    chart2_lookup = {body.name: body for body in chart2_bodies}
    
    # Compare each planet in chart1 with each planet in chart2
    for body1 in chart1_bodies:
        if body1.name not in ["Sun", "Moon", "Mercury", "Venus", "Mars", 
                              "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
            continue  # Only compare major planets
        
        for body2 in chart2_bodies:
            if body2.name not in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                                  "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
                continue
            
            # Skip same planet comparisons (e.g., Sun-Sun)
            if body1.name == body2.name:
                continue
            
            # Calculate angular distance
            pos1 = body1.sidereal_longitude if system == "sidereal" else body1.tropical_longitude
            pos2 = body2.sidereal_longitude if system == "sidereal" else body2.tropical_longitude
            
            angular_distance = abs(pos1 - pos2)
            if angular_distance > 180:
                angular_distance = 360 - angular_distance
            
            # Check for aspects
            for aspect_name, aspect_angle, orb in ASPECTS_CONFIG:
                # Check if within orb
                if abs(angular_distance - aspect_angle) <= orb:
                    # Calculate exact orb
                    exact_orb = abs(angular_distance - aspect_angle)
                    
                    # Calculate strength (closer to exact = stronger)
                    strength = 1.0 - (exact_orb / orb)
                    
                    aspect_data = {
                        "planet1": body1.name,
                        "planet2": body2.name,
                        "aspect": aspect_name,
                        "angle": aspect_angle,
                        "orb": round(exact_orb, 2),
                        "strength": round(strength, 3),
                        "score": ASPECT_SCORES.get(aspect_name, 1.0),
                        "system": system
                    }
                    aspects.append(aspect_data)
    
    # Sort by score (highest first)
    aspects.sort(key=lambda x: x["score"], reverse=True)
    
    return aspects


def calculate_house_overlays(
    chart1: NatalChart,
    chart2: NatalChart,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate house overlays - where chart2's planets fall in chart1's houses.
    
    Args:
        chart1: First chart (houses are from this chart)
        chart2: Second chart (planets are from this chart)
        system: "sidereal" or "tropical"
    
    Returns:
        Dictionary with house overlay information
    """
    overlays = {}
    
    # Get chart1's ascendant for house calculations
    asc1 = chart1.ascendant_data.get("sidereal_ascendant" if system == "sidereal" else "tropical_ascendant", 0)
    
    # Get chart2's planets
    chart2_bodies = chart2.celestial_bodies if system == "sidereal" else chart2.tropical_bodies
    
    for body in chart2_bodies:
        if body.name not in ["Sun", "Moon", "Mercury", "Venus", "Mars",
                            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]:
            continue
        
        pos = body.sidereal_longitude if system == "sidereal" else body.tropical_longitude
        
        # Calculate which house in chart1
        house_num, degrees_in_house = find_house_equal(pos, asc1)
        
        if house_num not in overlays:
            overlays[house_num] = []
        
        overlays[house_num].append({
            "planet": body.name,
            "position": round(pos, 4),
            "degrees_in_house": round(degrees_in_house, 2)
        })
    
    return overlays


def find_house_equal(sidereal_deg: float, ascendant: float) -> Tuple[int, float]:
    """
    Find which house a position falls into (equal house system).
    
    Args:
        sidereal_deg: Position in degrees
        ascendant: Ascendant position in degrees
    
    Returns:
        Tuple of (house_number, degrees_into_house)
    """
    for i in range(12):
        house_start = (ascendant + i * 30) % 360
        house_end = (house_start + 30) % 360
        
        if house_end < house_start:
            if sidereal_deg >= house_start or sidereal_deg < house_end:
                return i + 1, (sidereal_deg - house_start + 360) % 360
        elif house_start <= sidereal_deg < house_end:
            return i + 1, (sidereal_deg - house_start) % 360
    
    return 1, 0  # Default to first house


def calculate_compatibility_score(
    aspects: List[Dict[str, Any]],
    overlays: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate overall compatibility score based on aspects and overlays.
    
    Args:
        aspects: List of synastry aspects
        overlays: House overlay information
    
    Returns:
        Dictionary with compatibility scores and analysis
    """
    # Calculate aspect scores
    total_score = 0.0
    aspect_count = 0
    positive_aspects = 0
    challenging_aspects = 0
    
    positive_aspect_types = ["Conjunction", "Trine", "Sextile", "Quintile", "Biquintile"]
    challenging_aspect_types = ["Opposition", "Square", "Quincunx", "Semisquare", "Sesquiquadrate"]
    
    for aspect in aspects:
        total_score += aspect["score"] * aspect["strength"]
        aspect_count += 1
        
        if aspect["aspect"] in positive_aspect_types:
            positive_aspects += 1
        elif aspect["aspect"] in challenging_aspect_types:
            challenging_aspects += 1
    
    # Calculate average score
    avg_score = total_score / aspect_count if aspect_count > 0 else 0
    
    # Calculate compatibility percentage (0-100)
    # Normalize to 0-100 scale (assuming max score per aspect is ~5)
    compatibility_pct = min(100, (avg_score / 5.0) * 100) if aspect_count > 0 else 50
    
    # Analyze house overlays
    overlay_analysis = {}
    for house_num, planets in overlays.items():
        house_name = f"House {house_num}"
        overlay_analysis[house_name] = {
            "planets": [p["planet"] for p in planets],
            "count": len(planets)
        }
    
    return {
        "overall_score": round(compatibility_pct, 1),
        "aspect_count": aspect_count,
        "positive_aspects": positive_aspects,
        "challenging_aspects": challenging_aspects,
        "average_aspect_strength": round(avg_score, 2),
        "house_overlays": overlay_analysis,
        "interpretation": _interpret_compatibility(compatibility_pct, positive_aspects, challenging_aspects)
    }


def _interpret_compatibility(
    score: float,
    positive: int,
    challenging: int
) -> str:
    """
    Provide interpretation of compatibility score.
    
    Args:
        score: Compatibility score (0-100)
        positive: Number of positive aspects
        challenging: Number of challenging aspects
    
    Returns:
        Interpretation string
    """
    if score >= 80:
        return "Exceptional compatibility with strong harmonious connections"
    elif score >= 65:
        return "Good compatibility with mostly positive interactions"
    elif score >= 50:
        return "Moderate compatibility with balanced dynamics"
    elif score >= 35:
        return "Challenging compatibility requiring understanding and effort"
    else:
        return "Difficult compatibility with significant tensions to navigate"


def calculate_synastry(
    chart1: NatalChart,
    chart2: NatalChart,
    system: str = "sidereal"
) -> Dict[str, Any]:
    """
    Calculate complete synastry between two charts.
    
    Args:
        chart1: First birth chart
        chart2: Second birth chart
        system: "sidereal" or "tropical"
    
    Returns:
        Complete synastry analysis dictionary
    """
    try:
        # Calculate aspects
        chart1_bodies = chart1.celestial_bodies if system == "sidereal" else chart1.tropical_bodies
        chart2_bodies = chart2.celestial_bodies if system == "sidereal" else chart2.tropical_bodies
        
        aspects = calculate_synastry_aspects(chart1_bodies, chart2_bodies, system)
        
        # Calculate house overlays (chart2 planets in chart1 houses)
        overlays_1_2 = calculate_house_overlays(chart1, chart2, system)
        
        # Calculate house overlays (chart1 planets in chart2 houses)
        overlays_2_1 = calculate_house_overlays(chart2, chart1, system)
        
        # Calculate compatibility scores
        compatibility = calculate_compatibility_score(aspects, overlays_1_2)
        
        # Get top aspects
        top_aspects = aspects[:20]  # Top 20 aspects
        
        # Organize aspects by type
        aspects_by_type = {}
        for aspect in aspects:
            aspect_type = aspect["aspect"]
            if aspect_type not in aspects_by_type:
                aspects_by_type[aspect_type] = []
            aspects_by_type[aspect_type].append(aspect)
        
        return {
            "chart1_name": chart1.name,
            "chart2_name": chart2.name,
            "system": system,
            "compatibility": compatibility,
            "aspects": {
                "all": aspects,
                "top": top_aspects,
                "by_type": aspects_by_type,
                "count": len(aspects)
            },
            "house_overlays": {
                "chart2_in_chart1": overlays_1_2,
                "chart1_in_chart2": overlays_2_1
            },
            "summary": {
                "total_aspects": len(aspects),
                "compatibility_score": compatibility["overall_score"],
                "key_connections": [a for a in top_aspects[:5]]
            }
        }
    
    except Exception as e:
        logger.error(f"Error calculating synastry: {e}", exc_info=True)
        raise

