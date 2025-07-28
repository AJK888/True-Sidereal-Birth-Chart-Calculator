# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart, get_sign_and_ruler, format_true_sidereal_placement, PLANETS_CONFIG, 
    calculate_numerology, get_chinese_zodiac, TRUE_SIDEREAL_SIGNS,
    calculate_name_numerology
)
import swisseph as swe
import traceback
import requests
import pendulum
import os
import logging
from logtail import LogtailHandler
import google.generativeai as genai

# --- SETUP THE LOGGER ---
handler = None
logtail_token = os.getenv("LOGTAIL_SOURCE_TOKEN")
if logtail_token:
    ingesting_host = "https://s1450016.eu-nbg-2.betterstackdata.com"
    handler = LogtailHandler(source_token=logtail_token, host=ingesting_host)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if handler:
    logger.addHandler(handler)

# --- SETUP GEMINI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="True Sidereal API", version="1.0")

@app.get("/ping")
def ping():
    return {"message": "ok"}

origins = [
    "https://true-sidereal-birth-chart.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "HEAD"],
    allow_headers=["*"],
)

class ChartRequest(BaseModel):
    full_name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str
    unknown_time: bool = False

async def get_gemini_reading(chart_data: dict) -> str:
    """Formats a detailed, anonymized chart summary and gets a reading from Gemini Pro."""
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    try:
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        chinese_zodiac = chart_data.get("chinese_zodiac")
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        s_patterns = chart_data.get("sidereal_aspect_patterns", [])

        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)
        asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)
        
        prompt_parts = [
            "You are an expert astrologer and numerologist specializing in the True Sidereal system. Your task is to provide a warm, insightful, and comprehensive reading for a beginner based on the following anonymized data. Do not mention the raw data points in your response.",
            "First, deeply analyze and synthesize all the provided astrological and numerological data to understand the complete picture of the individual.\n"
        ]
        
        prompt_parts.append("**Astrological Data:**")
        if sun: prompt_parts.append(f"- Sun: {sun['position']}")
        if moon: prompt_parts.append(f"- Moon: {moon['position']}")
        if asc: prompt_parts.append(f"- Ascendant: {asc['position']}")
        if s_analysis.get("chart_ruler"): prompt_parts.append(f"- Chart Ruler: {s_analysis['chart_ruler']}")
        if s_analysis.get("dominant_planet"): prompt_parts.append(f"- Dominant Planet: {s_analysis['dominant_planet']}")
        if s_analysis.get("dominant_sign"): prompt_parts.append(f"- Dominant Sign: {s_analysis['dominant_sign']}")
        if s_analysis.get("dominant_element"): prompt_parts.append(f"- Dominant Element: {s_analysis['dominant_element']}")

        prompt_parts.append("\n**Numerological Data:**")
        if numerology_analysis.get("life_path_number"): prompt_parts.append(f"- Life Path Number: {numerology_analysis['life_path_number']}")
        if numerology_analysis.get("day_number"): prompt_parts.append(f"- Day Number: {numerology_analysis['day_number']}")
        if numerology_analysis.get("name_numerology"):
            name_nums = numerology_analysis['name_numerology']
            prompt_parts.append(f"- Expression Number: {name_nums.get('expression_number')}")
            prompt_parts.append(f"- Soul Urge Number: {name_nums.get('soul_urge_number')}")
            prompt_parts.append(f"- Personality Number: {name_nums.get('personality_number')}")
        if chinese_zodiac: prompt_parts.append(f"- Chinese Zodiac: {chinese_zodiac}")

        if s_patterns:
            prompt_parts.append("\n**Key Astrological Patterns:**")
            for pattern in s_patterns:
                prompt_parts.append(f"- {pattern}")
        
        top_aspects = s_aspects[:5]
        if top_aspects:
            prompt_parts.append("\n**Top 5 Strongest Aspects:**")
            for aspect in top_aspects:
                prompt_parts.append(f"- {aspect['p1_name']} {aspect['type']} {aspect['p2_name']}")

        prompt_parts.append("\n**Your Task:**")
        prompt_parts.append("Now, write a 3-4 paragraph reading that synthesizes this information for a beginner. Follow these steps:")
        prompt_parts.append("1. Begin by introducing the core identity, blending insights from the Sun, Moon, Ascendant, and the Life Path Number.")
        prompt_parts.append("2. Identify and explain the most unique or powerful themes in the chart. This could be a dominant element, a stellium pattern, or a particularly strong planet. Weave in the meaning of their Expression and Soul Urge numbers to show how these themes manifest as talents and desires.")
        prompt_parts.append("3. Briefly touch on how the key aspects create dynamic energy (harmony or tension) that shapes their personality and life experiences.")
        prompt_parts.append("4. Conclude with an encouraging summary of their overall energetic blueprint and potential path.")
        prompt_parts.append("Maintain a warm, positive, and educational tone throughout. Do not simply list traits; explain how they connect to form a complete person.")

        prompt = "\n".join(prompt_parts)

        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt)
        
        return response.text
        
    except Exception as e:
        print(f"Error getting Gemini reading: {e}")
        return "An error occurred while generating the AI reading."


@app.post("/calculate_chart")
async def calculate_chart_endpoint(data: ChartRequest):
    try:
        log_data = data.dict()
        if 'full_name' in log_data:
            log_data['chart_name'] = log_data.pop('full_name')
        logger.info("New chart request received", extra=log_data)

        swe.set_ephe_path(r".")

        opencage_key = os.getenv("OPENCAGE_KEY")
        if not opencage_key:
            raise HTTPException(status_code=500, detail="Server is missing the geocoding API key.")
        
        geo_url = f"https://api.opencagedata.com/geocode/v1/json?q={data.location}&key={opencage_key}"
        response = requests.get(geo_url, timeout=10)
        response.raise_for_status()
        geo_res = response.json()

        result = geo_res.get("results", [])[0] if geo_res.get("results") else {}
        geometry = result.get("geometry", {})
        annotations = result.get("annotations", {}).get("timezone", {})
        lat, lng, timezone_name = geometry.get("lat"), geometry.get("lng"), annotations.get("name")

        if not all([lat, lng, timezone_name]):
            raise HTTPException(status_code=400, detail="Could not retrieve complete location data.")

        local_time = pendulum.datetime(
            data.year, data.month, data.day, data.hour, data.minute, tz=timezone_name
        )
        utc_time = local_time.in_timezone('UTC')

        chart = NatalChart(
            name=data.full_name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng
        )
        chart.calculate_chart()
        
        numerology = calculate_numerology(data.day, data.month, data.year)
        name_numerology = calculate_name_numerology(data.full_name)
        chinese_zodiac = get_chinese_zodiac(data.year, data.month, data.day)
        
        house_rulers_formatted = {}
        if chart.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                cusp_deg = (chart.ascendant_data['sidereal_asc'] + i * 30) % 360
                sign, ruler_name = get_sign_and_ruler(cusp_deg)
                ruler_body = next((p for p in chart.sidereal_bodies if p.name == ruler_name), None)
                ruler_pos = f"– {ruler_body.formatted_position} – House {ruler_body.house_num}, {ruler_body.house_degrees}" if ruler_body and ruler_body.degree is not None else ""
                house_rulers_formatted[f"House {i+1}"] = f"{sign} (Ruler: {ruler_name} {ruler_pos})"
        
        major_positions_order = [
            'Ascendant', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
            'Uranus', 'Neptune', 'Pluto', 'Chiron', 'True Node', 'South Node',
            'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)'
        ]
        
        house_cusps = []
        if chart.ascendant_data.get("sidereal_asc") is not None:
            asc = chart.ascendant_data['sidereal_asc']
            house_cusps = [(asc + i * 30) % 360 for i in range(12)]

        full_response = {
            "name": chart.name, "utc_datetime": chart.utc_datetime_str, "location": chart.location_str,
            "day_night_status": chart.day_night_info.get("status", "N/A"),
            
            "chinese_zodiac": chinese_zodiac,
            "numerology_analysis": {
                "life_path_number": numerology["life_path"],
                "day_number": numerology["day_number"],
                "name_numerology": name_numerology
            },

            "sidereal_chart_analysis": {
                "chart_ruler": get_sign_and_ruler(chart.ascendant_data['sidereal_asc'])[1] if chart.ascendant_data.get('sidereal_asc') is not None else "N/A",
                "dominant_sign": f"{chart.sidereal_dominance.get('dominant_sign', 'N/A')} ({chart.sidereal_dominance.get('counts', {}).get('sign', {}).get(chart.sidereal_dominance.get('dominant_sign'), 0)} placements)",
                "dominant_element": f"{chart.sidereal_dominance.get('dominant_element', 'N/A')} ({chart.sidereal_dominance.get('counts', {}).get('element', {}).get(chart.sidereal_dominance.get('dominant_element'), 0)})",
                "dominant_modality": f"{chart.sidereal_dominance.get('dominant_modality', 'N/A')} ({chart.sidereal_dominance.get('counts', {}).get('modality', {}).get(chart.sidereal_dominance.get('dominant_modality'), 0)})",
                "dominant_planet": f"{chart.sidereal_dominance.get('dominant_planet', 'N/A')} (score {chart.sidereal_dominance.get('strength', {}).get(chart.sidereal_dominance.get('dominant_planet'), 0.0)})",
            },
            "sidereal_major_positions": [
                {"name": p.name, "position": p.formatted_position, "degrees": p.degree, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
                for p in sorted(chart.all_sidereal_points, key=lambda x: major_positions_order.index(x.name) if x.name in major_positions_order else 99) if p.name in major_positions_order
            ],
            "house_cusps": house_cusps,
            "sidereal_aspects": [
                {"p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}", "p1_degrees": a.p1.degree, "p2_degrees": a.p2.degree} for a in chart.sidereal_aspects
            ],
            "true_sidereal_signs": TRUE_SIDEREAL_SIGNS,
            "sidereal_aspect_patterns": [p['description'] for p in chart.sidereal_aspect_patterns],
            "sidereal_additional_points": [
                {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}", "retrograde": p.retrograde}
                for p in sorted(chart.all_sidereal_points, key=lambda x: x.name) if p.name not in major_positions_order
            ],
            "house_rulers": house_rulers_formatted,
            "house_sign_distributions": chart.house_sign_distributions,
            "unknown_time": data.unknown_time,
            "tropical_chart_analysis": {
                "dominant_sign": f"{chart.tropical_dominance.get('dominant_sign', 'N/A')} ({chart.tropical_dominance.get('counts', {}).get('sign', {}).get(chart.tropical_dominance.get('dominant_sign'), 0)} placements)",
                "dominant_element": f"{chart.tropical_dominance.get('dominant_element', 'N/A')} ({chart.tropical_dominance.get('counts', {}).get('element', {}).get(chart.tropical_dominance.get('dominant_element'), 0)})",
                "dominant_modality": f"{chart.tropical_dominance.get('dominant_modality', 'N/A')} ({chart.tropical_dominance.get('counts', {}).get('modality', {}).get(chart.tropical_dominance.get('dominant_modality'), 0)})",
                "dominant_planet": f"{chart.tropical_dominance.get('dominant_planet', 'N/A')} (score {chart.tropical_dominance.get('strength', {}).get(chart.tropical_dominance.get('dominant_planet'), 0.0)})",
            },
            "tropical_major_positions": [
                {"name": p.name, "position": p.formatted_position, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
                for p in sorted(chart.all_tropical_points, key=lambda x: major_positions_order.index(x.name) if x.name in major_positions_order else 99) if p.name in major_positions_order
            ],
            "tropical_aspects": [
                {"p1_name": f"{a.p1.name} in {a.p1.sign}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name} in {a.p2.sign}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}"} for a in chart.tropical_aspects
            ],
            "tropical_aspect_patterns": [p['description'] for p in chart.tropical_aspect_patterns],
            "tropical_additional_points": [
                {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}", "retrograde": p.retrograde}
                for p in sorted(chart.all_tropical_points, key=lambda x: x.name) if p.name not in major_positions_order
            ],
        }
        
        if data.unknown_time:
            # (Filtering logic remains the same)
            pass
        else:
            # Only get AI reading if time is known
            gemini_reading = await get_gemini_reading(full_response)
            full_response["gemini_reading"] = gemini_reading

        return full_response

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
