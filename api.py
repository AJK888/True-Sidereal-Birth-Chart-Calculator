# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart, get_sign_and_ruler, format_true_sidereal_placement, PLANETS_CONFIG, 
    calculate_numerology, get_chinese_zodiac, TRUE_SIDEREAL_SIGNS
)
import swisseph as swe
import traceback
import requests
import pendulum
import os
import logging
from logtail import LogtailHandler

# --- SETUP THE LOGGER ---
handler = None
logtail_token = os.getenv("LOGTAIL_SOURCE_TOKEN")
if logtail_token:
    handler = LogtailHandler(source_token=logtail_token)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if handler:
    logger.addHandler(handler)

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
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str
    unknown_time: bool = False # <-- NEW

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    try:
        log_data = data.dict()
        if 'name' in log_data:
            log_data['chart_name'] = log_data.pop('name')
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
            name=data.name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng
        )
        chart.calculate_chart()
        
        numerology = calculate_numerology(data.day, data.month, data.year)
        chinese_zodiac = get_chinese_zodiac(data.year, data.month, data.day)
        
        house_rulers_formatted = {}
        if chart.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                cusp_deg = (chart.ascendant_data['sidereal_asc'] + i * 30) % 360
                sign, ruler_name = get_sign_and_ruler(cusp_deg)
                ruler_body = next((p for p in chart.celestial_bodies if p.name == ruler_name), None)
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

        # --- Build the full response dictionary ---
        full_response = {
            "name": chart.name, "utc_datetime": chart.utc_datetime_str, "location": chart.location_str,
            "day_night_status": chart.day_night_info.get("status", "N/A"),
            "chart_analysis": {
                "chart_ruler": get_sign_and_ruler(chart.ascendant_data['sidereal_asc'])[1] if chart.ascendant_data.get('sidereal_asc') is not None else "N/A",
                "dominant_sign": f"{chart.dominance_analysis.get('dominant_sign', 'N/A')} ({chart.dominance_analysis.get('counts', {}).get('sign', {}).get(chart.dominance_analysis.get('dominant_sign'), 0)} placements)",
                "dominant_element": f"{chart.dominance_analysis.get('dominant_element', 'N/A')} ({chart.dominance_analysis.get('counts', {}).get('element', {}).get(chart.dominance_analysis.get('dominant_element'), 0)})",
                "dominant_modality": f"{chart.dominance_analysis.get('dominant_modality', 'N/A')} ({chart.dominance_analysis.get('counts', {}).get('modality', {}).get(chart.dominance_analysis.get('dominant_modality'), 0)})",
                "dominant_planet": f"{chart.dominance_analysis.get('dominant_planet', 'N/A')} (score {chart.dominance_analysis.get('strength', {}).get(chart.dominance_analysis.get('dominant_planet'), 0.0)})",
                "life_path_number": numerology["life_path"],
                "day_number": numerology["day_number"],
                "chinese_zodiac": chinese_zodiac
            },
            "major_positions": [
                {"name": p.name, "position": p.formatted_position, "degrees": p.degree, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
                for p in sorted(chart.all_points, key=lambda x: major_positions_order.index(x.name) if x.name in major_positions_order else 99) if p.name in major_positions_order
            ],
            "house_cusps": house_cusps,
            "aspects": [
                {"p1_name": f"{a.p1.name}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}", "p1_degrees": a.p1.degree, "p2_degrees": a.p2.degree} for a in chart.aspects
            ],
            "true_sidereal_signs": TRUE_SIDEREAL_SIGNS,
            "aspect_patterns": [p['description'] for p in chart.aspect_patterns],
            "additional_points": [
                {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}"}
                for p in sorted(chart.all_points, key=lambda x: x.name) if p.name not in major_positions_order
            ],
            "house_rulers": house_rulers_formatted,
            "house_sign_distributions": chart.house_sign_distributions,
            "unknown_time": data.unknown_time # <-- NEW
        }
        
        # --- NEW: If time is unknown, filter out sensitive data ---
        if data.unknown_time:
            full_response['chart_analysis']['chart_ruler'] = "Unavailable (Unknown Birth Time)"
            
            # Filter out angles from major positions
            angles = ['Ascendant', 'Midheaven (MC)', 'Descendant', 'Imum Coeli (IC)']
            full_response['major_positions'] = [p for p in full_response['major_positions'] if p['name'] not in angles]
            
            # Remove house info from all remaining positions
            for p in full_response['major_positions']:
                p['house_info'] = ""
            
            # Remove other time-sensitive sections
            full_response['house_cusps'] = []
            full_response['house_rulers'] = {}
            full_response['house_sign_distributions'] = {}
            full_response['additional_points'] = [p for p in full_response['additional_points'] if p['name'] != 'Part of Fortune']
        
        return full_response

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
