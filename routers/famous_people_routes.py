"""
Famous People Routes

API endpoints for finding similar famous people based on astrological charts.
"""

import json
import logging
from typing import Any
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from database import get_db, FamousPerson
from services.similarity_service import (
    calculate_comprehensive_similarity_score,
    check_strict_matches,
    check_aspect_matches,
    check_stellium_matches,
    extract_all_matching_factors,
    normalize_master_number,
    extract_top_aspects_from_chart
)

logger = logging.getLogger(__name__)

# Create router for famous people endpoints
router = APIRouter(prefix="/api", tags=["famous-people"])


class SimilarPeopleRequest(BaseModel):
    chart_data: Any  # Accept any type, we'll validate in endpoint
    limit: int = 10


@router.post("/find-similar-famous-people")
async def find_similar_famous_people_endpoint(
    request: Request,
    data: SimilarPeopleRequest,
    db: Session = Depends(get_db)
):
    """
    Find famous people with similar birth charts to the user's chart.
    This is a FREE feature - no subscription required.
    
    Args:
        chart_data: The user's calculated chart data (from /calculate_chart endpoint)
        limit: Number of matches to return (default 10, max 50)
    
    Returns:
        List of famous people sorted by similarity score
    """
    logger.info("="*60)
    logger.info("FAMOUS PEOPLE ENDPOINT CALLED")
    logger.info("="*60)
    try:
        limit = data.limit
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 10
        
        # Handle chart_data - it might come as a string (JSON) or dict
        chart_data = data.chart_data
        
        # Debug logging
        logger.info(f"Received chart_data type: {type(chart_data)}, is string: {isinstance(chart_data, str)}")
        if isinstance(chart_data, str):
            logger.info(f"chart_data string preview: {chart_data[:200]}")
        
        # Recursively parse JSON strings in nested structures
        def parse_json_recursive(obj):
            """Recursively parse JSON strings in nested structures."""
            if isinstance(obj, str):
                try:
                    parsed = json.loads(obj)
                    # If parsing succeeded, recursively parse the result
                    return parse_json_recursive(parsed)
                except (json.JSONDecodeError, TypeError):
                    # Not JSON, return as-is
                    return obj
            elif isinstance(obj, dict):
                return {k: parse_json_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [parse_json_recursive(item) for item in obj]
            else:
                return obj
        
        # Parse chart_data if it's a string
        if isinstance(chart_data, str):
            try:
                chart_data = json.loads(chart_data)
                logger.info(f"Parsed JSON string, new type: {type(chart_data)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse chart_data as JSON: {e}")
                raise HTTPException(status_code=400, detail="Invalid chart_data format - must be valid JSON")
        
        # Recursively parse any nested JSON strings (e.g., numerology, chinese_zodiac might be JSON strings)
        chart_data = parse_json_recursive(chart_data)
        
        # Debug: Log the types of nested values after recursive parsing
        if 'numerology' in chart_data:
            logger.info(f"numerology type after parsing: {type(chart_data['numerology'])}")
        if 'chinese_zodiac' in chart_data:
            logger.info(f"chinese_zodiac type after parsing: {type(chart_data['chinese_zodiac'])}")
        
        # Double-check it's a dict after parsing
        if not isinstance(chart_data, dict):
            logger.error(f"chart_data is not a dict after parsing. Type: {type(chart_data)}, Value: {str(chart_data)[:200]}")
            raise HTTPException(status_code=400, detail=f"chart_data must be a dictionary or JSON string. Got type: {type(chart_data).__name__}")
        
        # Ensure we have the expected structure
        if 'sidereal_major_positions' not in chart_data and 'tropical_major_positions' not in chart_data:
            logger.warning(f"chart_data missing expected keys. Keys present: {list(chart_data.keys())[:10]}")
        
        # Extract user's signs for filtering (optimization)
        # Safely handle missing or invalid data
        sidereal_positions = chart_data.get('sidereal_major_positions', [])
        tropical_positions = chart_data.get('tropical_major_positions', [])
        
        # Ensure positions are lists
        if not isinstance(sidereal_positions, list):
            logger.warning(f"sidereal_major_positions is not a list: {type(sidereal_positions)}")
            sidereal_positions = []
        if not isinstance(tropical_positions, list):
            logger.warning(f"tropical_major_positions is not a list: {type(tropical_positions)}")
            tropical_positions = []
        
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
        
        # Get user's numerology and Chinese zodiac for additional filtering
        # Safely handle nested dictionaries that might be strings or missing
        # Safely get numerology - it might be a string, dict, or missing.
        # Prefer "numerology", but fall back to "numerology_analysis" used in chart responses.
        numerology_data = chart_data.get('numerology')
        if numerology_data is None and 'numerology_analysis' in chart_data:
            numerology_data = chart_data.get('numerology_analysis')
        if numerology_data is None:
            numerology_data = {}
        elif isinstance(numerology_data, str):
            try:
                numerology_data = json.loads(numerology_data)
                # Recursively parse in case it contains more nested strings
                numerology_data = parse_json_recursive(numerology_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse numerology as JSON: {e}, value: {numerology_data[:100] if isinstance(numerology_data, str) else numerology_data}")
                numerology_data = {}
        elif not isinstance(numerology_data, dict):
            logger.warning(f"numerology is not a dict: {type(numerology_data)}")
            numerology_data = {}
        
        # Now safely get the life_path_number
        user_life_path = numerology_data.get('life_path_number') if isinstance(numerology_data, dict) else None
        
        # Safely get chinese_zodiac animal - extract only animal (last word), not element
        chinese_zodiac_data = chart_data.get('chinese_zodiac')
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
        
        # OPTIMIZATION: Filter database query using new matching criteria
        # We'll use broader filters to catch all potential matches, then apply strict criteria
        
        # Build filter query - use OR to catch any potential matches
        query = db.query(FamousPerson)
        
        # Build conditions for potential matches
        conditions = []
        
        # 1. Sun AND Moon sidereal match
        if user_sun_s and user_moon_s:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_sidereal == user_sun_s,
                    FamousPerson.moon_sign_sidereal == user_moon_s
                )
            )
        
        # 2. Sun AND Moon tropical match
        if user_sun_t and user_moon_t:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_tropical == user_sun_t,
                    FamousPerson.moon_sign_tropical == user_moon_t
                )
            )
        
        # 3. Numerology day AND life path match
        user_day = numerology_data.get('day_number') if isinstance(numerology_data, dict) else None
        if user_day and user_life_path:
            user_day_norm = normalize_master_number(user_day)
            user_lp_norm = normalize_master_number(user_life_path)
            # Build OR conditions for master numbers
            lp_conditions = []
            for lp in user_lp_norm:
                lp_conditions.append(FamousPerson.life_path_number == lp)
            day_conditions = []
            for day in user_day_norm:
                day_conditions.append(FamousPerson.day_number == day)
            if lp_conditions and day_conditions:
                conditions.append(
                    and_(
                        or_(*lp_conditions),
                        or_(*day_conditions)
                    )
                )
        
        # 4. Chinese zodiac AND (day OR life path)
        if user_chinese_animal:
            chinese_conditions = []
            chinese_conditions.append(FamousPerson.chinese_zodiac_animal.ilike(f"%{user_chinese_animal}%"))
            
            numer_conditions = []
            if user_day:
                user_day_norm = normalize_master_number(user_day)
                for day in user_day_norm:
                    numer_conditions.append(FamousPerson.day_number == day)
            if user_life_path:
                user_lp_norm = normalize_master_number(user_life_path)
                for lp in user_lp_norm:
                    numer_conditions.append(FamousPerson.life_path_number == lp)
            
            if numer_conditions:
                conditions.append(
                    and_(
                        chinese_conditions[0],
                        or_(*numer_conditions)
                    )
                )
        
        # Also include people who might match on aspects or stelliums
        # (they need chart_data_json or top_aspects_json)
        if not conditions:
            # If no strict conditions, at least require chart data for aspect/stellium matching
            conditions.append(FamousPerson.chart_data_json.isnot(None))
        else:
            # Add aspect/stellium candidates to the OR conditions
            conditions.extend([
                FamousPerson.top_aspects_json.isnot(None),
                FamousPerson.chart_data_json.isnot(None)
            ])
        
        # Apply filters - use OR to get all potential matches
        if conditions:
            query = query.filter(or_(*conditions))
        else:
            # Fallback: at least match one sign
            sign_conditions = []
            if user_sun_s:
                sign_conditions.append(FamousPerson.sun_sign_sidereal == user_sun_s)
            if user_sun_t:
                sign_conditions.append(FamousPerson.sun_sign_tropical == user_sun_t)
            if user_moon_s:
                sign_conditions.append(FamousPerson.moon_sign_sidereal == user_moon_s)
            if user_moon_t:
                sign_conditions.append(FamousPerson.moon_sign_tropical == user_moon_t)
            if sign_conditions:
                query = query.filter(or_(*sign_conditions))
        
        # Get ALL famous people with chart data (no filtering, search entire database)
        # Only require that they have chart data for scoring
        logger.info("Querying database for famous people with chart data...")
        all_famous_people = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None)
        ).all()
        
        logger.info(f"Found {len(all_famous_people)} famous people in database with chart data")
        
        if not all_famous_people:
            logger.warning("No famous people found in database with chart data")
            return {
                "matches": [],
                "message": "No matches found. We're constantly adding more famous people to our database. Check back soon!"
            }
        
        # Calculate comprehensive scores for ALL famous people
        logger.info(f"Calculating similarity scores for {len(all_famous_people)} famous people...")
        matches = []
        scores_calculated = 0
        for fp in all_famous_people:
            # Calculate comprehensive score for everyone
            comprehensive_score = calculate_comprehensive_similarity_score(chart_data, fp)
            scores_calculated += 1
            
            # Only include if score > 0 (has actual matches)
            if comprehensive_score > 0.0:
                # Check match types for display purposes
                strict_match, strict_reasons = check_strict_matches(
                    chart_data, fp, numerology_data, chinese_zodiac_data
                )
                aspect_match, aspect_reasons = check_aspect_matches(chart_data, fp)
                stellium_match, stellium_reasons = check_stellium_matches(chart_data, fp)
                
                # Combine all match reasons
                all_reasons = strict_reasons + aspect_reasons + stellium_reasons
                
                # Determine match type for display
                match_type = "strict" if strict_match else ("aspect" if aspect_match else ("stellium" if stellium_match else "general"))
                
                matches.append({
                    "famous_person": fp,
                    "similarity_score": comprehensive_score,
                    "match_reasons": all_reasons,
                    "match_type": match_type
                })
        
        logger.info(f"Calculated scores for {scores_calculated} people, found {len(matches)} with score > 0")
        
        # Sort by similarity score ONLY (highest first)
        matches.sort(key=lambda m: m["similarity_score"], reverse=True)
        
        # Take top 20 matches (always return top 20 from entire database)
        top_matches = matches[:20]
        logger.info(f"Returning top {len(top_matches)} matches")
        
        # Format response with comprehensive matching details
        result = []
        for match in top_matches:
            fp = match["famous_person"]
            
            # Get planetary placements if available
            fp_planetary = {}
            if fp.planetary_placements_json:
                try:
                    fp_planetary = json.loads(fp.planetary_placements_json)
                except:
                    pass
            
            # Get chart data
            fp_chart = {}
            if fp.chart_data_json:
                try:
                    fp_chart = json.loads(fp.chart_data_json)
                except:
                    pass
            
            # Extract all matching factors
            matching_factors = extract_all_matching_factors(chart_data, fp, fp_planetary, fp_chart)
            
            # Build match details
            match_details = {
                "name": fp.name,
                "wikipedia_url": fp.wikipedia_url,
                "occupation": fp.occupation,
                "similarity_score": round(match["similarity_score"], 1),
                "matching_factors": matching_factors,  # List of all matching factors
                "match_reasons": match.get("match_reasons", []),  # Keep for backward compatibility
                "match_type": match.get("match_type", "general"),
                "birth_date": f"{fp.birth_month}/{fp.birth_day}/{fp.birth_year}",
                "birth_location": fp.birth_location,
            }
            
            result.append(match_details)
        
        logger.info(f"Endpoint returning {len(result)} matches out of {len(all_famous_people)} compared")
        
        return {
            "matches": result,
            "total_compared": len(all_famous_people),  # Fixed: was famous_people, now all_famous_people
            "matches_found": len(result)
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error finding similar famous people: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error finding similar famous people: {str(e)}")

