"""
Similarity Service for Famous People Matching

This module contains all the business logic for calculating similarity scores
and matching users with famous people based on astrological data.
"""

import json
import logging
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from database import FamousPerson

logger = logging.getLogger(__name__)


def extract_stelliums(chart_data: dict) -> dict:
    """
    Extract stelliums from chart data (both sidereal and tropical).
    Returns dict with 'sidereal' and 'tropical' lists of stellium descriptions.
    """
    stelliums = {"sidereal": [], "tropical": []}
    
    # Extract from aspect patterns
    s_patterns = chart_data.get('sidereal_aspect_patterns', [])
    t_patterns = chart_data.get('tropical_aspect_patterns', [])
    
    for pattern in s_patterns:
        desc = pattern.get('description', '')
        if 'stellium' in desc.lower():
            stelliums['sidereal'].append(desc)
    
    for pattern in t_patterns:
        desc = pattern.get('description', '')
        if 'stellium' in desc.lower():
            stelliums['tropical'].append(desc)
    
    return stelliums


def extract_top_aspects_from_chart(chart_data: dict, top_n: int = 3) -> dict:
    """
    Extract top N aspects from chart data (both sidereal and tropical).
    Returns dict with 'sidereal' and 'tropical' lists of aspect dicts.
    """
    aspects = {"sidereal": [], "tropical": []}
    
    # Get sidereal aspects
    sidereal_aspects = chart_data.get('sidereal_aspects', [])
    sorted_sidereal = sorted(
        sidereal_aspects,
        key=lambda a: (
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").isdigit() else 0,
            abs(float(str(a.get("orb", "999")).replace("°", "").strip()) if isinstance(a.get("orb"), str) else float(a.get("orb", 999)))
        )
    )[:top_n]
    
    for aspect in sorted_sidereal:
        p1_name = aspect.get("p1_name", "").split(" in ")[0].strip()
        p2_name = aspect.get("p2_name", "").split(" in ")[0].strip()
        aspects["sidereal"].append({
            "p1": p1_name,
            "p2": p2_name,
            "type": aspect.get("type", ""),
        })
    
    # Get tropical aspects
    tropical_aspects = chart_data.get('tropical_aspects', [])
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
        })
    
    return aspects


def normalize_master_number(num_str):
    """Normalize master numbers (e.g., '33/6' -> ['33', '6'])"""
    if not num_str:
        return []
    num_str = str(num_str)
    if '/' in num_str:
        return [num_str.split('/')[0], num_str.split('/')[-1]]
    return [num_str]


def check_strict_matches(user_chart_data: dict, famous_person: FamousPerson, user_numerology: dict, user_chinese_zodiac: dict) -> tuple[bool, list[str]]:
    """
    Check if famous person matches strict criteria:
    1. Sun AND Moon in sidereal
    2. Sun AND Moon in tropical
    3. Numerology day AND life path number
    4. Chinese zodiac AND (numerology day OR life path number)
    
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    matches = []
    
    # Extract user's signs
    s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', [])}
    t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', [])}
    
    def extract_sign(position_str):
        if not position_str:
            return None
        parts = position_str.split()
        return parts[-1] if parts else None
    
    user_sun_s = extract_sign(s_positions.get('Sun', {}).get('position')) if 'Sun' in s_positions else None
    user_moon_s = extract_sign(s_positions.get('Moon', {}).get('position')) if 'Moon' in s_positions else None
    user_sun_t = extract_sign(t_positions.get('Sun', {}).get('position')) if 'Sun' in t_positions else None
    user_moon_t = extract_sign(t_positions.get('Moon', {}).get('position')) if 'Moon' in t_positions else None
    
    # 1. Check Sun AND Moon in sidereal
    if user_sun_s and user_moon_s and famous_person.sun_sign_sidereal and famous_person.moon_sign_sidereal:
        if user_sun_s == famous_person.sun_sign_sidereal and user_moon_s == famous_person.moon_sign_sidereal:
            matches.append("strict_sun_moon_sidereal")
            reasons.append(f"Matching Sun ({user_sun_s}) and Moon ({user_moon_s}) in Sidereal")
    
    # 2. Check Sun AND Moon in tropical
    if user_sun_t and user_moon_t and famous_person.sun_sign_tropical and famous_person.moon_sign_tropical:
        if user_sun_t == famous_person.sun_sign_tropical and user_moon_t == famous_person.moon_sign_tropical:
            matches.append("strict_sun_moon_tropical")
            reasons.append(f"Matching Sun ({user_sun_t}) and Moon ({user_moon_t}) in Tropical")
    
    # 3. Check numerology day AND life path number
    user_day = user_numerology.get('day_number') if isinstance(user_numerology, dict) else None
    user_life_path = user_numerology.get('life_path_number') if isinstance(user_numerology, dict) else None
    
    if user_day and user_life_path and famous_person.day_number and famous_person.life_path_number:
        user_day_norm = normalize_master_number(user_day)
        fp_day_norm = normalize_master_number(famous_person.day_number)
        user_lp_norm = normalize_master_number(user_life_path)
        fp_lp_norm = normalize_master_number(famous_person.life_path_number)
        
        day_match = any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm)
        lp_match = any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm)
        
        if day_match and lp_match:
            matches.append("strict_numerology")
            reasons.append(f"Matching Day Number ({user_day}) and Life Path Number ({user_life_path})")
    
    # 4. Check Chinese zodiac AND (numerology day OR life path number)
    user_chinese = user_chinese_zodiac.get('animal') if isinstance(user_chinese_zodiac, dict) else None
    if user_chinese and famous_person.chinese_zodiac_animal:
        if user_chinese.lower() == famous_person.chinese_zodiac_animal.lower():
            # Check if also matches numerology day
            if user_day and famous_person.day_number:
                user_day_norm = normalize_master_number(user_day)
                fp_day_norm = normalize_master_number(famous_person.day_number)
                if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                    matches.append("strict_chinese_day")
                    reasons.append(f"Matching Chinese Zodiac ({user_chinese}) and Day Number ({user_day})")
            
            # Check if also matches life path number
            if user_life_path and famous_person.life_path_number:
                user_lp_norm = normalize_master_number(user_life_path)
                fp_lp_norm = normalize_master_number(famous_person.life_path_number)
                if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                    matches.append("strict_chinese_lifepath")
                    reasons.append(f"Matching Chinese Zodiac ({user_chinese}) and Life Path Number ({user_life_path})")
    
    return len(matches) > 0, reasons


def check_aspect_matches(user_chart_data: dict, famous_person: FamousPerson) -> tuple[bool, list[str]]:
    """
    Check if famous person shares 2 of the top 3 aspects.
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    
    # Get user's top 3 aspects
    user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=3)
    
    # Get famous person's top 3 aspects
    if not famous_person.top_aspects_json:
        return False, []
    
    try:
        fp_aspects = json.loads(famous_person.top_aspects_json)
    except:
        return False, []
    
    # Compare sidereal aspects
    user_s_aspects = user_aspects.get('sidereal', [])
    fp_s_aspects = fp_aspects.get('sidereal', [])
    
    s_matches = 0
    matched_aspects_s = []
    for u_aspect in user_s_aspects:
        for fp_aspect in fp_s_aspects:
            # Check if same planets and same aspect type (order doesn't matter)
            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                s_matches += 1
                matched_aspects_s.append(f"{u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                break
    
    # Compare tropical aspects
    user_t_aspects = user_aspects.get('tropical', [])
    fp_t_aspects = fp_aspects.get('tropical', [])
    
    t_matches = 0
    matched_aspects_t = []
    for u_aspect in user_t_aspects:
        for fp_aspect in fp_t_aspects:
            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                t_matches += 1
                matched_aspects_t.append(f"{u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                break
    
    # Need at least 2 matches total (can be from either system)
    total_matches = s_matches + t_matches
    
    if total_matches >= 2:
        if matched_aspects_s:
            reasons.append(f"Sharing {s_matches} top aspect(s) in Sidereal: {', '.join(matched_aspects_s)}")
        if matched_aspects_t:
            reasons.append(f"Sharing {t_matches} top aspect(s) in Tropical: {', '.join(matched_aspects_t)}")
        return True, reasons
    
    return False, []


def check_stellium_matches(user_chart_data: dict, famous_person: FamousPerson) -> tuple[bool, list[str]]:
    """
    Check if famous person has the same stelliums.
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    
    # Get user's stelliums
    user_stelliums = extract_stelliums(user_chart_data)
    
    # Get famous person's stelliums
    if not famous_person.chart_data_json:
        return False, []
    
    try:
        fp_chart = json.loads(famous_person.chart_data_json)
        fp_stelliums = extract_stelliums(fp_chart)
    except:
        return False, []
    
    # Compare stelliums (extract sign/house from description)
    def extract_stellium_key(desc):
        """Extract key info from stellium description"""
        # Format: "4 bodies in Aquarius (Air, Fixed Sign Stellium)" or "3 bodies in House 5 (House Stellium)"
        if 'Sign Stellium' in desc:
            # Extract sign name
            parts = desc.split(' bodies in ')
            if len(parts) > 1:
                sign = parts[1].split(' (')[0].strip()
                return ('sign', sign)
        elif 'House Stellium' in desc:
            # Extract house number
            parts = desc.split('House ')
            if len(parts) > 1:
                house = parts[1].split(' (')[0].strip()
                return ('house', house)
        return None
    
    matched_stelliums = []
    
    # Compare sidereal stelliums
    for u_stellium in user_stelliums.get('sidereal', []):
        u_key = extract_stellium_key(u_stellium)
        if u_key:
            for fp_stellium in fp_stelliums.get('sidereal', []):
                fp_key = extract_stellium_key(fp_stellium)
                if u_key == fp_key:
                    matched_stelliums.append(f"Sidereal: {u_stellium}")
                    break
    
    # Compare tropical stelliums
    for u_stellium in user_stelliums.get('tropical', []):
        u_key = extract_stellium_key(u_stellium)
        if u_key:
            for fp_stellium in fp_stelliums.get('tropical', []):
                fp_key = extract_stellium_key(fp_stellium)
                if u_key == fp_key:
                    matched_stelliums.append(f"Tropical: {u_stellium}")
                    break
    
    if matched_stelliums:
        reasons.extend([f"Shared stellium: {s}" for s in matched_stelliums])
        return True, reasons
    
    return False, []


def calculate_comprehensive_similarity_score(user_chart_data: dict, famous_person: FamousPerson) -> float:
    """
    Calculate comprehensive similarity score including all placements and aspects.
    Returns a score from 0-100.
    """
    try:
        # Load famous person's chart data
        if not famous_person.chart_data_json:
            return 0.0
        
        fp_chart = json.loads(famous_person.chart_data_json)
        fp_planetary_placements = {}
        if famous_person.planetary_placements_json:
            try:
                parsed = json.loads(famous_person.planetary_placements_json)
                # Ensure it's a dict, not a string
                if isinstance(parsed, dict):
                    fp_planetary_placements = parsed
            except:
                pass
        
        score = 0.0
        max_possible_score = 0.0
        
        # Extract user's positions
        s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', [])}
        t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', [])}
        s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', [])}
        t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', [])}
        
        # Helper function to extract sign from position string
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        # ========================================================================
        # PLANETARY PLACEMENTS (Sidereal & Tropical) - All planets
        # ========================================================================
        
        # All planets to compare (weighted by importance)
        planets_to_compare = [
            ('Sun', 5.0),      # 5 per system → 10 total (sidereal + tropical)
            ('Moon', 5.0),     # 5 per system → 10 total
            ('Mercury', 3.0),  # 3 per system → 6 total
            ('Venus', 3.0),    # 3 per system → 6 total
            ('Mars', 2.0),     # 2 per system → 4 total
            ('Jupiter', 2.0),  # 2 per system → 4 total
            ('Saturn', 2.0),   # 2 per system → 4 total
            ('Uranus', 2.0),   # 2 per system → 4 total
            ('Neptune', 2.0),  # 2 per system → 4 total
            ('Pluto', 2.0),    # 2 per system → 4 total
        ]
        
        for planet_name, weight in planets_to_compare:
            # Sidereal comparison
            user_planet_s = None
            fp_planet_s = None
            
            if planet_name in s_positions:
                user_planet_s = extract_sign(s_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if isinstance(fp_planetary_placements, dict) and fp_planetary_placements.get('sidereal', {}).get(planet_name):
                fp_planet_s = fp_planetary_placements['sidereal'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_sidereal:
                fp_planet_s = famous_person.sun_sign_sidereal
            elif planet_name == 'Moon' and famous_person.moon_sign_sidereal:
                fp_planet_s = famous_person.moon_sign_sidereal
            # Fallback to chart_data_json
            elif fp_chart.get('sidereal_major_positions'):
                for p in fp_chart['sidereal_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_s = extract_sign(p.get('position'))
                        break
            
            if user_planet_s and fp_planet_s:
                max_possible_score += weight
                if user_planet_s == fp_planet_s:
                    score += weight
            
            # Tropical comparison
            user_planet_t = None
            fp_planet_t = None
            
            if planet_name in t_positions:
                user_planet_t = extract_sign(t_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if isinstance(fp_planetary_placements, dict) and fp_planetary_placements.get('tropical', {}).get(planet_name):
                fp_planet_t = fp_planetary_placements['tropical'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_tropical:
                fp_planet_t = famous_person.sun_sign_tropical
            elif planet_name == 'Moon' and famous_person.moon_sign_tropical:
                fp_planet_t = famous_person.moon_sign_tropical
            # Fallback to chart_data_json
            elif fp_chart.get('tropical_major_positions'):
                for p in fp_chart['tropical_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_t = extract_sign(p.get('position'))
                        break
            
            if user_planet_t and fp_planet_t:
                max_possible_score += weight
                if user_planet_t == fp_planet_t:
                    score += weight
        
        # Rising/Ascendant is intentionally EXCLUDED from similarity scoring per user request.
        # We keep the code paths simple by not adding any Rising-based contributions here.
        
        # ========================================================================
        # ASPECTS (Top 3 from both systems)
        # ========================================================================
        # If at least 2 out of 3 top aspects match, award 15 points
        
        user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=3)
        
        if famous_person.top_aspects_json:
            try:
                fp_aspects = json.loads(famous_person.top_aspects_json)
                
                # Count matching aspects in sidereal
                sidereal_matches = 0
                user_s_aspects = user_aspects.get('sidereal', [])
                fp_s_aspects = fp_aspects.get('sidereal', [])
                
                for u_aspect in user_s_aspects:
                    for fp_aspect in fp_s_aspects:
                        u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                        fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                        if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                            sidereal_matches += 1
                            break
                
                # Count matching aspects in tropical
                tropical_matches = 0
                user_t_aspects = user_aspects.get('tropical', [])
                fp_t_aspects = fp_aspects.get('tropical', [])
                
                for u_aspect in user_t_aspects:
                    for fp_aspect in fp_t_aspects:
                        u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                        fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                        if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                            tropical_matches += 1
                            break
                
                # Award 15 points if at least 2 out of 3 aspects match in either system
                if sidereal_matches >= 2 or tropical_matches >= 2:
                    max_possible_score += 15.0
                    score += 15.0
            except:
                pass
        
        # ========================================================================
        # NUMEROLOGY
        # ========================================================================
        # On the user side, numerology is usually under "numerology_analysis" in the
        # chart response, but older/other flows may use "numerology". Support both.
        raw_numerology = (
            user_chart_data.get('numerology')
            or user_chart_data.get('numerology_analysis')
            or {}
        )
        if isinstance(raw_numerology, str):
            try:
                raw_numerology = json.loads(raw_numerology)
            except Exception:
                raw_numerology = {}
        if not isinstance(raw_numerology, dict):
            raw_numerology = {}
        
        # Life Path Number - weight: 10 points
        user_life_path = raw_numerology.get('life_path_number')
        fp_life_path = famous_person.life_path_number
        
        if user_life_path and fp_life_path:
            max_possible_score += 10.0
            user_lp_norm = normalize_master_number(user_life_path)
            fp_lp_norm = normalize_master_number(fp_life_path)
            
            if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                score += 10.0
        
        # Day Number - weight: 10 points
        user_day_num = raw_numerology.get('day_number')
        fp_day_num = famous_person.day_number
        
        if user_day_num and fp_day_num:
            max_possible_score += 10.0
            user_day_norm = normalize_master_number(user_day_num)
            fp_day_norm = normalize_master_number(fp_day_num)
            
            if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                score += 10.0
        
        # ========================================================================
        # CHINESE ZODIAC
        # ========================================================================
        # In the chart response, chinese_zodiac is usually a string like "Earth Tiger".
        # Extract only the animal (last word) - we don't match on element.
        raw_chinese = user_chart_data.get('chinese_zodiac', {})
        if isinstance(raw_chinese, str):
            # Extract animal (last word) from strings like "Earth Tiger" -> "Tiger"
            parts = raw_chinese.strip().split()
            if len(parts) >= 1:
                user_chinese_animal = parts[-1]  # Take last word (the animal)
            else:
                user_chinese_animal = None
        elif isinstance(raw_chinese, dict):
            user_chinese_animal = raw_chinese.get('animal')
        else:
            user_chinese_animal = None
        
        # Chinese Zodiac Animal - weight: 10 points (only match animal, not element)
        fp_chinese_animal = famous_person.chinese_zodiac_animal
        
        if user_chinese_animal and fp_chinese_animal:
            max_possible_score += 10.0
            if user_chinese_animal.lower() == fp_chinese_animal.lower():
                score += 10.0
        
        # ========================================================================
        # DOMINANT ELEMENT - Not included in similarity calculation
        # ========================================================================
        # Dominant Element is NOT included in scoring or matching_factors per user requirements
        
        # ========================================================================
        # CALCULATE FINAL SCORE
        # ========================================================================
        
        # Normalize to 0-100 scale based on maximum possible score
        if max_possible_score > 0:
            normalized_score = (score / max_possible_score) * 100.0
        else:
            # If max_possible_score is 0, it means no planetary placements were found to compare
            # This could happen if chart data structure is unexpected
            # Log this for debugging
            logger.warning(
                f"max_possible_score is 0 for {famous_person.name if famous_person else 'unknown'}. "
                f"Score: {score}, "
                f"User has sidereal: {bool(user_chart_data.get('sidereal_major_positions'))}, "
                f"User has tropical: {bool(user_chart_data.get('tropical_major_positions'))}, "
                f"FP has placements: {bool(fp_planetary_placements)}, "
                f"FP has chart: {bool(fp_chart)}"
            )
            # If we have matches (strict/aspect/stellium), give a minimum score
            # Otherwise return 0
            normalized_score = 0.0
        
        result = min(normalized_score, 100.0)
        return result
    
    except Exception as e:
        logger.error(f"Error calculating comprehensive similarity: {e}", exc_info=True)
        return 0.0


def extract_all_matching_factors(user_chart_data: dict, fp: FamousPerson, fp_planetary: dict, fp_chart: dict) -> list:
    """Extract a detailed list of all matching factors between user and famous person."""
    matches_list = []
    
    # Extract user's positions
    s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', []) if isinstance(p, dict) and 'name' in p}
    t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', []) if isinstance(p, dict) and 'name' in p}
    s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', []) if isinstance(p, dict) and 'name' in p}
    t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', []) if isinstance(p, dict) and 'name' in p}
    
    def extract_sign(position_str):
        if not position_str:
            return None
        parts = position_str.split()
        return parts[-1] if parts else None
    
    # All planets to check
    planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
    
    # Check each planet in both systems
    for planet_name in planets:
        # Sidereal
        user_planet_s = None
        fp_planet_s = None
        
        if planet_name in s_positions:
            user_planet_s = extract_sign(s_positions[planet_name].get('position'))
        
        if fp_planetary.get('sidereal', {}).get(planet_name):
            fp_planet_s = fp_planetary['sidereal'][planet_name].get('sign')
        elif planet_name == 'Sun' and fp.sun_sign_sidereal:
            fp_planet_s = fp.sun_sign_sidereal
        elif planet_name == 'Moon' and fp.moon_sign_sidereal:
            fp_planet_s = fp.moon_sign_sidereal
        elif fp_chart.get('sidereal_major_positions'):
            for p in fp_chart['sidereal_major_positions']:
                if p.get('name') == planet_name:
                    fp_planet_s = extract_sign(p.get('position'))
                    break
        
        if user_planet_s and fp_planet_s and user_planet_s == fp_planet_s:
            matches_list.append(f"{planet_name} (Sidereal)")
        
        # Tropical
        user_planet_t = None
        fp_planet_t = None
        
        if planet_name in t_positions:
            user_planet_t = extract_sign(t_positions[planet_name].get('position'))
        
        if fp_planetary.get('tropical', {}).get(planet_name):
            fp_planet_t = fp_planetary['tropical'][planet_name].get('sign')
        elif planet_name == 'Sun' and fp.sun_sign_tropical:
            fp_planet_t = fp.sun_sign_tropical
        elif planet_name == 'Moon' and fp.moon_sign_tropical:
            fp_planet_t = fp.moon_sign_tropical
        elif fp_chart.get('tropical_major_positions'):
            for p in fp_chart['tropical_major_positions']:
                if p.get('name') == planet_name:
                    fp_planet_t = extract_sign(p.get('position'))
                    break
        
        if user_planet_t and fp_planet_t and user_planet_t == fp_planet_t:
            matches_list.append(f"{planet_name} (Tropical)")
    
    # Check Rising/Ascendant (if birth time known)
    if not user_chart_data.get('unknown_time') and not fp.unknown_time:
        user_rising_s = None
        user_rising_t = None
        fp_rising_s = None
        fp_rising_t = None
        
        if 'Ascendant' in s_extra:
            asc_info = s_extra['Ascendant'].get('info', '')
            user_rising_s = asc_info.split()[0] if asc_info else None
        
        if 'Ascendant' in t_extra:
            asc_info = t_extra['Ascendant'].get('info', '')
            user_rising_t = asc_info.split()[0] if asc_info else None
        
        if fp_chart.get('sidereal_additional_points'):
            for p in fp_chart['sidereal_additional_points']:
                if p.get('name') == 'Ascendant':
                    asc_info = p.get('info', '')
                    fp_rising_s = asc_info.split()[0] if asc_info else None
                    break
        
        if fp_chart.get('tropical_additional_points'):
            for p in fp_chart['tropical_additional_points']:
                if p.get('name') == 'Ascendant':
                    asc_info = p.get('info', '')
                    fp_rising_t = asc_info.split()[0] if asc_info else None
                    break
        
        if user_rising_s and fp_rising_s and user_rising_s == fp_rising_s:
            matches_list.append("Rising/Ascendant (Sidereal)")
        
        if user_rising_t and fp_rising_t and user_rising_t == fp_rising_t:
            matches_list.append("Rising/Ascendant (Tropical)")
    
    # Check Numerology
    raw_numerology = (
        user_chart_data.get('numerology')
        or user_chart_data.get('numerology_analysis')
        or {}
    )
    if isinstance(raw_numerology, str):
        try:
            raw_numerology = json.loads(raw_numerology)
        except Exception:
            raw_numerology = {}
    if not isinstance(raw_numerology, dict):
        raw_numerology = {}
    
    user_life_path = raw_numerology.get('life_path_number') if isinstance(raw_numerology, dict) else None
    user_day = raw_numerology.get('day_number') if isinstance(raw_numerology, dict) else None
    
    if user_life_path and fp.life_path_number:
        user_lp_norm = normalize_master_number(user_life_path)
        fp_lp_norm = normalize_master_number(fp.life_path_number)
        if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
            matches_list.append(f"Life Path Number ({user_life_path})")
    
    if user_day and fp.day_number:
        user_day_norm = normalize_master_number(user_day)
        fp_day_norm = normalize_master_number(fp.day_number)
        if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
            matches_list.append(f"Day Number ({user_day})")
    
    # Check Chinese Zodiac - only match animal, not element
    raw_chinese = user_chart_data.get('chinese_zodiac', {})
    if isinstance(raw_chinese, str):
        # Extract animal (last word) from strings like "Earth Tiger" -> "Tiger"
        parts = raw_chinese.strip().split()
        if len(parts) >= 1:
            user_chinese_animal = parts[-1]  # Take last word (the animal)
        else:
            user_chinese_animal = None
    elif isinstance(raw_chinese, dict):
        user_chinese_animal = raw_chinese.get('animal')
    else:
        user_chinese_animal = None
    
    if user_chinese_animal and fp.chinese_zodiac_animal:
        if user_chinese_animal.lower() == fp.chinese_zodiac_animal.lower():
            matches_list.append(f"Chinese Zodiac ({user_chinese_animal})")
    
    # Dominant Element is NOT included in similarity matching (removed per user request)
    
    # Check Aspects (from match_reasons if available, or calculate)
    user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=10)
    if fp.top_aspects_json:
        try:
            fp_aspects = json.loads(fp.top_aspects_json)
            
            # Check sidereal aspects
            user_s_aspects = user_aspects.get('sidereal', [])
            fp_s_aspects = fp_aspects.get('sidereal', [])
            for u_aspect in user_s_aspects:
                for fp_aspect in fp_s_aspects:
                    u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                    fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                    if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                        matches_list.append(f"Aspect (Sidereal): {u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                        break
            
            # Check tropical aspects
            user_t_aspects = user_aspects.get('tropical', [])
            fp_t_aspects = fp_aspects.get('tropical', [])
            for u_aspect in user_t_aspects:
                for fp_aspect in fp_t_aspects:
                    u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                    fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                    if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                        matches_list.append(f"Aspect (Tropical): {u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                        break
        except:
            pass
    
    return matches_list


async def find_similar_famous_people_internal(
    chart_data: dict,
    limit: int = 10,
    db: Optional[Session] = None
) -> dict:
    """
    Internal function to find similar famous people (for use in reading generation).
    Returns the same format as the endpoint but can be called internally.
    """
    if not db:
        logger.warning("No database session provided to find_similar_famous_people_internal")
        return {"matches": [], "total_compared": 0, "matches_found": 0}
    
    logger.info("Starting find_similar_famous_people_internal - searching for famous people matches")
    
    try:
        # Extract user's signs (same as endpoint)
        sidereal_positions = chart_data.get('sidereal_major_positions', [])
        tropical_positions = chart_data.get('tropical_major_positions', [])
        
        s_positions = {p['name']: p for p in sidereal_positions if isinstance(p, dict) and 'name' in p}
        t_positions = {p['name']: p for p in tropical_positions if isinstance(p, dict) and 'name' in p}
        
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        user_sun_s = extract_sign(s_positions.get('Sun', {}).get('position')) if 'Sun' in s_positions and s_positions['Sun'].get('position') else None
        user_sun_t = extract_sign(t_positions.get('Sun', {}).get('position')) if 'Sun' in t_positions and t_positions['Sun'].get('position') else None
        user_moon_s = extract_sign(s_positions.get('Moon', {}).get('position')) if 'Moon' in s_positions and s_positions['Moon'].get('position') else None
        user_moon_t = extract_sign(t_positions.get('Moon', {}).get('position')) if 'Moon' in t_positions and t_positions['Moon'].get('position') else None
        
        # Get numerology and Chinese zodiac from chart data
        # Numerology may be under "numerology" or "numerology_analysis"
        numerology_data = (
            chart_data.get('numerology')
            or chart_data.get('numerology_analysis')
            or {}
        )
        if isinstance(numerology_data, str):
            try:
                numerology_data = json.loads(numerology_data)
            except Exception:
                numerology_data = {}
        if not isinstance(numerology_data, dict):
            numerology_data = {}
        
        # Chinese zodiac - extract only animal (last word), not element
        chinese_zodiac_data = chart_data.get('chinese_zodiac', {})
        if isinstance(chinese_zodiac_data, str):
            # Extract animal (last word) from strings like "Earth Tiger" -> "Tiger"
            parts = chinese_zodiac_data.strip().split()
            if len(parts) >= 1:
                user_chinese_animal = parts[-1]  # Take last word (the animal)
            else:
                user_chinese_animal = None
        elif isinstance(chinese_zodiac_data, dict):
            user_chinese_animal = chinese_zodiac_data.get('animal')
        else:
            user_chinese_animal = None
        
        user_life_path = numerology_data.get('life_path_number')
        user_day = numerology_data.get('day_number')
        
        # Build query (same logic as endpoint)
        query = db.query(FamousPerson)
        conditions = []
        
        if user_sun_s and user_moon_s:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_sidereal == user_sun_s,
                    FamousPerson.moon_sign_sidereal == user_moon_s
                )
            )
        
        if user_sun_t and user_moon_t:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_tropical == user_sun_t,
                    FamousPerson.moon_sign_tropical == user_moon_t
                )
            )
        
        if user_day and user_life_path:
            user_day_norm = normalize_master_number(user_day)
            user_lp_norm = normalize_master_number(user_life_path)
            lp_conditions = [FamousPerson.life_path_number == lp for lp in user_lp_norm]
            day_conditions = [FamousPerson.day_number == day for day in user_day_norm]
            if lp_conditions and day_conditions:
                conditions.append(and_(or_(*lp_conditions), or_(*day_conditions)))
        
        if user_chinese_animal:
            chinese_conditions = [FamousPerson.chinese_zodiac_animal.ilike(f"%{user_chinese_animal}%")]
            numer_conditions = []
            if user_day:
                user_day_norm = normalize_master_number(user_day)
                numer_conditions.extend([FamousPerson.day_number == day for day in user_day_norm])
            if user_life_path:
                user_lp_norm = normalize_master_number(user_life_path)
                numer_conditions.extend([FamousPerson.life_path_number == lp for lp in user_lp_norm])
            if numer_conditions:
                conditions.append(and_(chinese_conditions[0], or_(*numer_conditions)))
        
        if not conditions:
            conditions.append(FamousPerson.chart_data_json.isnot(None))
        else:
            conditions.extend([
                FamousPerson.top_aspects_json.isnot(None),
                FamousPerson.chart_data_json.isnot(None)
            ])
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        # Get ALL famous people with chart data (search entire database)
        all_famous_people = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None)
        ).all()
        
        logger.info(f"Found {len(all_famous_people)} famous people with chart data to compare")
        
        if not all_famous_people:
            logger.warning("No famous people found in database with chart data")
            return {"matches": [], "total_compared": 0, "matches_found": 0}
        
        # Calculate comprehensive scores for ALL famous people
        matches = []
        for fp in all_famous_people:
            # Calculate comprehensive score for everyone
            comprehensive_score = calculate_comprehensive_similarity_score(chart_data, fp)
            
            # Only include if score > 0 (has actual matches)
            if comprehensive_score > 0.0:
                strict_match, strict_reasons = check_strict_matches(chart_data, fp, numerology_data, chinese_zodiac_data)
                aspect_match, aspect_reasons = check_aspect_matches(chart_data, fp)
                stellium_match, stellium_reasons = check_stellium_matches(chart_data, fp)
                
                all_reasons = strict_reasons + aspect_reasons + stellium_reasons
                
                # Determine match type
                match_type = "strict" if strict_match else ("aspect" if aspect_match else ("stellium" if stellium_match else "general"))
                
                # Get planetary placements and chart data
                fp_planetary = {}
                if fp.planetary_placements_json:
                    try:
                        fp_planetary = json.loads(fp.planetary_placements_json)
                    except:
                        pass
                
                fp_chart = {}
                if fp.chart_data_json:
                    try:
                        fp_chart = json.loads(fp.chart_data_json)
                    except:
                        pass
                
                # Use the existing extract_all_matching_factors function
                matching_factors = extract_all_matching_factors(chart_data, fp, fp_planetary, fp_chart)
                
                matches.append({
                    "famous_person": fp,
                    "similarity_score": comprehensive_score,
                    "match_reasons": all_reasons,
                    "match_type": match_type,
                    "matching_factors": matching_factors
                })
        
        # Sort by similarity score ONLY (highest first)
        matches.sort(key=lambda m: m["similarity_score"], reverse=True)
        
        # Always return top 40 from entire database
        top_matches = matches[:40]
        
        logger.info(f"Found {len(matches)} matches with score > 0, returning top {len(top_matches)}")
        
        # Format response
        result = []
        for match in top_matches:
            fp = match["famous_person"]
            result.append({
                "name": fp.name,
                "occupation": fp.occupation,
                "similarity_score": round(match["similarity_score"], 1),
                "matching_factors": match.get("matching_factors", []),
                "birth_date": f"{fp.birth_month}/{fp.birth_day}/{fp.birth_year}",
                "birth_location": fp.birth_location,
            })
        
        logger.info(f"find_similar_famous_people_internal completed: {len(result)} matches returned")
        
        return {
            "matches": result,
            "total_compared": len(all_famous_people),
            "matches_found": len(result)
        }
    
    except Exception as e:
        logger.error(f"Error in find_similar_famous_people_internal: {e}", exc_info=True)
        return {"matches": [], "total_compared": 0, "matches_found": 0}

