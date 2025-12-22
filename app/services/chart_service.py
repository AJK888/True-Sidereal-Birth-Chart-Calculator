"""
⚠️ PRESERVATION ZONE - Chart Service

This module contains chart formatting and utility functions.
NOTE: Actual chart calculations are in natal_chart.py and MUST NOT be modified.

This service only contains:
- Chart formatting functions (get_full_text_report, format_full_report_for_email)
- Chart utility functions (generate_chart_hash, get_quick_highlights)
- Chart parsing functions (parse_pasted_chart_data)

CRITICAL: Do NOT include any calculation logic here. All calculations are in natal_chart.py.
"""

import json
import hashlib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def generate_chart_hash(chart_data: Dict, unknown_time: bool) -> str:
    """Generate a unique hash from chart data for caching."""
    # Create a stable representation of the chart data
    key_data = {
        'unknown_time': unknown_time,
        'major_positions': chart_data.get('sidereal_major_positions', []),
        'aspects': chart_data.get('sidereal_aspects', [])
    }
    # Sort lists to ensure consistent hashing
    if isinstance(key_data['major_positions'], list):
        key_data['major_positions'] = sorted(key_data['major_positions'], key=lambda x: x.get('name', ''))
    if isinstance(key_data['aspects'], list):
        key_data['aspects'] = sorted(key_data['aspects'], key=lambda x: (x.get('p1_name', ''), x.get('p2_name', '')))
    
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]  # Use first 16 chars


def get_full_text_report(res: dict) -> str:
    """Format chart data as a full text report."""
    out = f"=== SIDEREAL CHART: {res.get('name', 'N/A')} ===\n"
    out += f"- UTC Date & Time: {res.get('utc_datetime', 'N/A')}{' (Noon Estimate)' if res.get('unknown_time') else ''}\n"
    out += f"- Location: {res.get('location', 'N/A')}\n"
    out += f"- Day/Night Determination: {res.get('day_night_status', 'N/A')}\n\n"
    
    out += f"--- CHINESE ZODIAC ---\n"
    out += f"- Your sign is the {res.get('chinese_zodiac', 'N/A')}\n\n"

    if res.get('numerology_analysis'):
        numerology = res['numerology_analysis']
        out += f"--- NUMEROLOGY REPORT ---\n"
        out += f"- Life Path Number: {numerology.get('life_path_number', 'N/A')}\n"
        out += f"- Day Number: {numerology.get('day_number', 'N/A')}\n"
        if numerology.get('name_numerology'):
            name_numerology = numerology['name_numerology']
            out += f"\n-- NAME NUMEROLOGY --\n"
            out += f"- Expression (Destiny) Number: {name_numerology.get('expression_number', 'N/A')}\n"
            out += f"- Soul Urge Number: {name_numerology.get('soul_urge_number', 'N/A')}\n"
            out += f"- Personality Number: {name_numerology.get('personality_number', 'N/A')}\n"
    
    if res.get('sidereal_chart_analysis'):
        analysis = res['sidereal_chart_analysis']
        out += f"\n-- SIDEREAL CHART ANALYSIS --\n"
        out += f"- Chart Ruler: {analysis.get('chart_ruler', 'N/A')}\n"
        out += f"- Dominant Sign: {analysis.get('dominant_sign', 'N/A')}\n"
        out += f"- Dominant Element: {analysis.get('dominant_element', 'N/A')}\n"
        out += f"- Dominant Modality: {analysis.get('dominant_modality', 'N/A')}\n"
        out += f"- Dominant Planet: {analysis.get('dominant_planet', 'N/A')}\n\n"
        
    out += f"--- MAJOR POSITIONS ---\n"
    if res.get('sidereal_major_positions'):
        for p in res['sidereal_major_positions']:
            line = f"- {p.get('name', '')}: {p.get('position', '')}"
            if p.get('name') not in ['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node']:
                line += f" ({p.get('percentage', 0)}%)"
            if p.get('retrograde'): line += " (Rx)"
            if p.get('house_info'): line += f" {p.get('house_info')}"
            out += f"{line}\n"

    if res.get('sidereal_retrogrades'):
        out += f"\n--- RETROGRADE PLANETS (Energy turned inward) ---\n"
        for p in res['sidereal_retrogrades']:
            out += f"- {p.get('name', 'N/A')}\n"

    out += f"\n--- MAJOR ASPECTS (ranked by influence score) ---\n"
    if res.get('sidereal_aspects'):
        for a in res['sidereal_aspects']:
            out += f"- {a.get('p1_name','')} {a.get('type','')} {a.get('p2_name','')} (orb {a.get('orb','')}, score {a.get('score','')})\n"
    else:
        out += "- No major aspects detected.\n"
        
    out += f"\n--- ASPECT PATTERNS ---\n"
    if res.get('sidereal_aspect_patterns'):
        for p in res['sidereal_aspect_patterns']:
            line = f"- {p.get('description', '')}"
            if p.get('orb'): line += f" (avg orb {p.get('orb')})"
            if p.get('score'): line += f" (score {p.get('score')})"
            out += f"{line}\n"
    else:
        out += "- No major aspect patterns detected.\n"

    if not res.get('unknown_time'):
        out += f"\n--- ADDITIONAL POINTS & ANGLES ---\n"
        if res.get('sidereal_additional_points'):
            for p in res['sidereal_additional_points']:
                line = f"- {p.get('name', '')}: {p.get('info', '')}"
                if p.get('retrograde'): line += " (Rx)"
                out += f"{line}\n"
        out += f"\n--- HOUSE RULERS ---\n"
        if res.get('house_rulers'):
            for house, info in res['house_rulers'].items():
                out += f"- {house}: {info}\n"
        out += f"\n--- HOUSE SIGN DISTRIBUTIONS ---\n"
        if res.get('house_sign_distributions'):
            for house, segments in res['house_sign_distributions'].items():
                out += f"{house}:\n"
                if segments:
                    for seg in segments:
                        out += f"      - {seg}\n"
    else:
        out += f"\n- (House Rulers, House Distributions, and some additional points require a known birth time and are not displayed.)\n"

    if res.get('tropical_major_positions'):
        out += f"\n\n\n=== TROPICAL CHART ===\n\n"
        trop_analysis = res.get('tropical_chart_analysis', {})
        out += f"-- CHART ANALYSIS --\n"
        out += f"- Dominant Sign: {trop_analysis.get('dominant_sign', 'N/A')}\n"
        out += f"- Dominant Element: {trop_analysis.get('dominant_element', 'N/A')}\n"
        out += f"- Dominant Modality: {trop_analysis.get('dominant_modality', 'N/A')}\n"
        out += f"- Dominant Planet: {trop_analysis.get('dominant_planet', 'N/A')}\n\n"
        out += f"--- MAJOR POSITIONS ---\n"
        for p in res['tropical_major_positions']:
            line = f"- {p.get('name', '')}: {p.get('position', '')}"
            if p.get('name') not in ['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node']:
                line += f" ({p.get('percentage', 0)}%)"
            if p.get('retrograde'): line += " (Rx)"
            if p.get('house_info'): line += f" {p.get('house_info')}"
            out += f"{line}\n"

        if res.get('tropical_retrogrades'):
            out += f"\n--- RETROGRADE PLANETS (Energy turned inward) ---\n"
            for p in res['tropical_retrogrades']:
                out += f"- {p.get('name', 'N/A')}\n"

        out += f"\n--- MAJOR ASPECTS (ranked by influence score) ---\n"
        if res.get('tropical_aspects'):
            for a in res['tropical_aspects']:
                out += f"- {a.get('p1_name','')} {a.get('type','')} {a.get('p2_name','')} (orb {a.get('orb','')}, score {a.get('score','')})\n"
        else:
            out += "- No major aspects detected.\n"
            
        out += f"\n--- ASPECT PATTERNS ---\n"
        if res.get('tropical_aspect_patterns'):
            for p in res['tropical_aspect_patterns']:
                line = f"- {p.get('description', '')}"
                if p.get('orb'): line += f" (avg orb {p.get('orb')})"
                if p.get('score'): line += f" (score {p.get('score')})"
                out += f"{line}\n"
        else:
            out += "- No major aspect patterns detected.\n"
            
        if not res.get('unknown_time'):
            out += f"\n--- ADDITIONAL POINTS & ANGLES ---\n"
            if res.get('tropical_additional_points'):
                for p in res['tropical_additional_points']:
                    line = f"- {p.get('name', '')}: {p.get('info', '')}"
                    if p.get('retrograde'): line += " (Rx)"
                    out += f"{line}\n"
    return out


def format_full_report_for_email(chart_data: dict, reading_text: str, user_inputs: dict, chart_image_base64: Optional[str], include_inputs: bool = True) -> str:
    """Format full report for email (deprecated - PDF generation is used instead)."""
    html = "<h1>Synthesis Astrology Report</h1>"
    
    if include_inputs:
        html += "<h2>Chart Inputs</h2>"
        html += f"<p><b>Name:</b> {user_inputs.get('full_name', 'N/A')}</p>"
        html += f"<p><b>Birth Date:</b> {user_inputs.get('birth_date', 'N/A')}</p>"
        html += f"<p><b>Birth Time:</b> {user_inputs.get('birth_time', 'N/A')}</p>"
        html += f"<p><b>Location:</b> {user_inputs.get('location', 'N/A')}</p>"
        html += "<hr>"

    if chart_image_base64:
        html += "<h2>Natal Chart Wheel</h2>"
        html += f'<img src="data:image/svg+xml;base64,{chart_image_base64}" alt="Natal Chart Wheel" width="600">'
        html += "<hr>"

    html += "<h2>AI Astrological Synthesis</h2>"
    html += f"<p>{reading_text.replace('\\n', '<br><br>')}</p>"
    html += "<hr>"

    full_text_report = get_full_text_report(chart_data)
    html += "<h2>Full Astrological Data</h2>"
    html += f"<pre>{full_text_report}</pre>"
    
    return f"<html><head><style>body {{ font-family: sans-serif; }} pre {{ white-space: pre-wrap; word-wrap: break-word; }} img {{ max-width: 100%; height: auto; }}</style></head><body>{html}</body></html>"


def _sign_from_position(pos: str | None) -> str | None:
    """Extract sign from a position string like '12°34' Virgo'."""
    if not pos or pos == "N/A":
        return None
    parts = pos.split()
    return parts[-1] if parts else None


def get_quick_highlights(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate quick highlights from chart data without using AI.
    Returns a plain text string with bullet points about key chart features.
    """
    # Prepare lookups
    s_pos = {p["name"]: p for p in chart_data.get("sidereal_major_positions", [])}
    t_pos = {p["name"]: p for p in chart_data.get("tropical_major_positions", [])}
    s_extra = {p["name"]: p for p in chart_data.get("sidereal_additional_points", [])}
    t_extra = {p["name"]: p for p in chart_data.get("tropical_additional_points", [])}
    s_analysis = chart_data.get("sidereal_chart_analysis", {}) or {}
    t_analysis = chart_data.get("tropical_chart_analysis", {}) or {}
    numerology = chart_data.get("numerology_analysis", {}) or {}
    
    lines = []
    
    # Identity triad line (Sun, Moon, Asc)
    sun_s = _sign_from_position(s_pos.get("Sun", {}).get("position"))
    sun_t = _sign_from_position(t_pos.get("Sun", {}).get("position"))
    moon_s = _sign_from_position(s_pos.get("Moon", {}).get("position"))
    moon_t = _sign_from_position(t_pos.get("Moon", {}).get("position"))
    
    if not unknown_time:
        asc_s = _sign_from_position(s_pos.get("Ascendant", {}).get("position"))
        asc_t = _sign_from_position(t_pos.get("Ascendant", {}).get("position"))
    else:
        asc_s = asc_t = None
    
    headline_parts = []
    if sun_s:
        headline_parts.append(f"Sidereal Sun in {sun_s}")
    if sun_t:
        headline_parts.append(f"Tropical Sun in {sun_t}")
    if moon_s:
        headline_parts.append(f"Sidereal Moon in {moon_s}")
    if moon_t:
        headline_parts.append(f"Tropical Moon in {moon_t}")
    if not unknown_time and asc_s:
        headline_parts.append(f"Sidereal Ascendant in {asc_s}")
    if not unknown_time and asc_t:
        headline_parts.append(f"Tropical Ascendant in {asc_t}")
    
    if headline_parts:
        lines.append(" • " + " | ".join(headline_parts))
    
    # Dominant element & planet
    dom_elem_s = s_analysis.get("dominant_element")
    dom_planet_s = s_analysis.get("dominant_planet")
    
    if dom_elem_s or dom_planet_s:
        text = "You have a strong "
        if dom_elem_s:
            text += dom_elem_s.lower() + " emphasis"
        if dom_elem_s and dom_planet_s:
            text += " and a "
        if dom_planet_s:
            text += f"{dom_planet_s} signature"
        text += ", which shapes how you instinctively move through life."
        lines.append(" • " + text)
    
    # Nodal / life direction headline
    nn_pos = s_pos.get("True Node", {}) or {}
    nn_sign = _sign_from_position(nn_pos.get("position"))
    
    if nn_sign:
        lines.append(
            f" • Your Sidereal North Node in {nn_sign} points to a lifetime of growing into the qualities of that sign."
        )
    
    # Numerology quick hook
    life_path = numerology.get("life_path_number")
    if life_path:
        lines.append(
            f" • Life Path {life_path} adds a repeating lesson about how you define success and meaning in this life."
        )
    
    # One or two strongest aspects
    aspects = chart_data.get("sidereal_aspects", []) or []
    if aspects:
        def _parse_aspect_score(score_val):
            """Convert score string to float."""
            if isinstance(score_val, (int, float)):
                return float(score_val)
            if isinstance(score_val, str):
                try:
                    return float(score_val)
                except (ValueError, TypeError):
                    return 0.0
            return 0.0
        
        def _parse_aspect_orb(orb_val):
            """Convert orb string (e.g., '2.34°') to float."""
            if isinstance(orb_val, (int, float)):
                return abs(float(orb_val))
            if isinstance(orb_val, str):
                try:
                    # Remove degree symbol and any whitespace, then convert
                    orb_clean = orb_val.replace('°', '').strip()
                    return abs(float(orb_clean))
                except (ValueError, TypeError):
                    return 999.0
            return 999.0
        
        aspects_sorted = sorted(
            aspects,
            key=lambda a: (-_parse_aspect_score(a.get("score", 0)), _parse_aspect_orb(a.get("orb", 999)))
        )
        top_aspects = aspects_sorted[:2]
        
        for a in top_aspects:
            p1 = a.get("p1_name", "Body 1")
            p2 = a.get("p2_name", "Body 2")
            atype = a.get("type", "aspect")
            atype_lower = atype.lower() if atype else ""
            
            if atype_lower in ("conjunction", "trine", "sextile"):
                vibe = "natural talent or ease"
            elif atype_lower in ("square", "opposition"):
                vibe = "core tension you are learning to work with"
            else:
                vibe = "distinct pattern in your personality"
            
            lines.append(
                f" • {p1} {atype} {p2} marks a {vibe} that keeps showing up across your life."
            )
    
    # Fallback if nothing available
    if not lines:
        return "Quick highlights are unavailable for this chart."
    
    # Return final text
    intro = "Quick Highlights From Your Chart"
    body = "\n".join(lines)
    return f"{intro}\n{body}"


def parse_pasted_chart_data(pasted_text: str) -> Dict[str, Any]:
    """
    Parse pasted chart data and full reading text.
    Extracts structured information from the pasted text.
    """
    result = {
        "full_reading": "",
        "chart_data": {},
        "core_identity": {"sidereal": {}, "tropical": {}},
        "planetary_placements": {"sidereal": [], "tropical": []},
        "major_aspects": [],
        "numerology": {},
        "chinese_zodiac": "",
        "unknown_time": True
    }
    
    # Try to extract full reading (usually at the beginning or end)
    # Look for common reading section markers
    reading_markers = [
        "Snapshot: What Will Feel Most True About You",
        "Chart Overview and Core Themes",
        "Your Astrological Blueprint",
        "Major Life Dynamics"
    ]
    
    reading_start = -1
    for marker in reading_markers:
        idx = pasted_text.find(marker)
        if idx != -1:
            reading_start = idx
            break
    
    if reading_start != -1:
        # Extract reading (everything before structured data sections)
        result["full_reading"] = pasted_text[:reading_start].strip()
        structured_data = pasted_text[reading_start:]
    else:
        # Assume all text is reading if no markers found
        result["full_reading"] = pasted_text
        structured_data = ""
    
    # Parse structured sections
    lines = pasted_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect sections
        if "=== SIDEREAL" in line.upper() or "SIDEREAL CHART" in line.upper():
            current_section = "sidereal"
        elif "=== TROPICAL" in line.upper() or "TROPICAL CHART" in line.upper():
            current_section = "tropical"
        elif "CORE IDENTITY" in line.upper():
            current_section = "core_identity"
        elif "MAJOR POSITIONS" in line.upper() or "PLANETARY PLACEMENTS" in line.upper():
            current_section = "placements"
        elif "MAJOR ASPECTS" in line.upper():
            current_section = "aspects"
        elif "NUMEROLOGY" in line.upper():
            current_section = "numerology"
        elif "CHINESE ZODIAC" in line.upper():
            current_section = "chinese_zodiac"
        elif "UNKNOWN TIME" in line.upper():
            result["unknown_time"] = "true" in line.lower()
        
        # Parse placements
        if current_section == "placements" and ":" in line:
            # Format: "Sun: 25°30' Capricorn – House 10, 15°30'"
            parts = line.split(":")
            if len(parts) == 2:
                planet = parts[0].strip()
                position = parts[1].strip()
                result["planetary_placements"]["sidereal"].append({
                    "planet": planet,
                    "position": position
                })
        
        # Parse aspects
        if current_section == "aspects" and ("conjunction" in line.lower() or "opposition" in line.lower() or 
                                               "trine" in line.lower() or "square" in line.lower() or 
                                               "sextile" in line.lower()):
            result["major_aspects"].append(line)
        
        # Parse numerology
        if current_section == "numerology":
            if "life path" in line.lower():
                result["numerology"]["life_path"] = line
            elif "day number" in line.lower():
                result["numerology"]["day_number"] = line
            elif "expression" in line.lower():
                result["numerology"]["expression"] = line
        
        # Parse Chinese zodiac
        if current_section == "chinese_zodiac" and not result["chinese_zodiac"]:
            result["chinese_zodiac"] = line
    
    return result

