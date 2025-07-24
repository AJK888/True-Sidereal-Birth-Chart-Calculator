import os
import traceback
import pendulum
import requests
import swisseph as swe
import logging
from logtail import LogtailHandler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart,
    PLANETS_CONFIG,
    calculate_numerology,
    format_true_sidereal_placement,
    get_chinese_zodiac,
    get_sign_and_ruler,
)

# --- SETUP THE LOGGER ---
handler = None
logtail_token = os.getenv("LOGTAIL_SOURCE_TOKEN")
if logtail_token:
    handler = LogtailHandler(source_token=logtail_token)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if handler:
    logger.addHandler(handler)

# 1. Create the app object first.
app = FastAPI(title="True Sidereal API", version="1.0")

# 2. Add middleware.
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

# 3. Define the Pydantic model.
class ChartRequest(BaseModel):
    name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str

# 4. Define the routes.
@app.get("/ping")
def ping():
    return {"message": "ok"}

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    try:
        # Log the incoming request
        log_data = data.dict()
        logger.info("New chart request received", extra=log_data)

        swe.set_ephe_path(r".")

        # --- SECURE GEOCODING ON BACKEND ---
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

        # --- TIMEZONE CONVERSION ON BACKEND using Pendulum ---
        local_time = pendulum.datetime(
            data.year, data.month, data.day, data.hour, data.minute, tz=timezone_name
        )
        utc_time = local_time.in_timezone('UTC')

        # --- MAIN CHART CALCULATION ---
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
        
        # --- FORMAT FINAL JSON RESPONSE ---
        return {
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
                {"name": p.name, "position": p.formatted_position, "percentage": p.sign_percentage, "retrograde": p.retrograde, "house_info": f"– House {p.house_num}, {p.house_degrees}" if p.house_num > 0 else ""}
                for p in sorted(chart.all_points, key=lambda x: major_positions_order.index(x.name) if x.name in major_positions_order else 99) if p.name in major_positions_order
            ],
            "aspects": [
                {"p1_name": f"{a.p1.name}{' (Rx)' if a.p1.retrograde else ''}", "p2_name": f"{a.p2.name}{' (Rx)' if a.p2.retrograde else ''}", "type": a.type, "orb": f"{abs(a.orb):.2f}°", "score": f"{a.strength:.2f}"} for a in chart.aspects
            ],
            "aspect_patterns": [p['description'] for p in chart.aspect_patterns],
            "additional_points": [
                {"name": p.name, "info": f"{p.formatted_position} – House {p.house_num}, {p.house_degrees}"}
                for p in sorted(chart.all_points, key=lambda x: x.name) if p.name not in major_positions_order
            ],
            "house_rulers": house_rulers_formatted,
            "house_sign_distributions": chart.house_sign_distributions
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log the full error to your logging service
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        # Also print to console for live debugging on Render
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
