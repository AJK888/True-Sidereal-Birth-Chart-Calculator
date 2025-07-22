# api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from natal_chart import (
    NatalChart, get_sign_and_ruler, format_true_sidereal_placement, PLANETS_CONFIG, 
    calculate_numerology, get_chinese_zodiac
)
from fastapi.middleware.cors import CORSMiddleware
import swisseph as swe
import traceback
import requests
import pendulum

# 1. The app object must be created FIRST.
app = FastAPI(title="True Sidereal API", version="1.0")

# 2. THEN, you can define routes like /ping.
@app.get("/ping")
def ping():
    return {"message": "ok"}

# 3. And then add middleware.
origins = [
    "https://true-sidereal-chart.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

class ChartRequest(BaseModel):
    name: str; year: int; month: int; day: int;
    hour: int; minute: int; location: str

@app.post("/calculate_chart")
def calculate_chart_endpoint(data: ChartRequest):
    try:
        swe.set_ephe_path(r".")

        # --- SECURE GEOCODING ON BACKEND ---
        opencage_key = "122d238a65bc443297d6144ba105975d"
        geo_url = f"https://api.opencagedata.com/geocode/v1/json?q={data.location}&key={opencage_key}"
        geo_res = requests.get(geo_url, timeout=10).json()

        if not geo_res or not geo_res.get("results"):
            raise HTTPException(status_code=400, detail="Location could not be found.")
        
        result = geo_res["results"][0]
        lat = result["geometry"]["lat"]
        lng = result["geometry"]["lng"]
        timezone_name = result["annotations"]["timezone"]["name"]

        # --- TIMEZONE CONVERSION ON BACKEND using Pendulum ---
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
        
        # (The rest of the file is unchanged)
        house_rulers_formatted = {}
        if chart.ascendant_data.get("sidereal_asc") is not None:
            for i in range(12):
                cusp_deg = (chart.ascendant_data['sidereal_asc'] + i * 30) % 360
                sign, ruler_name = get_sign_and_ruler(cusp_deg)
                ruler_body = next((p for p in chart.celestial_bodies if p.name == ruler_name), None)
                ruler_pos = f"– {ruler_body.formatted_position} – House {ruler_body.house_num}, {ruler_body.house_degrees}" if ruler_body and ruler_body.degree is not None else ""
                house_rulers_formatted[f"House {i+1}"] = f"{sign} (Ruler: {ruler_name} {ruler_pos})"

        sunrise_utc, sunset_utc = "N/A", "N/A"
        if chart.day_night_info.get("sunrise") is not None: sunrise_utc = f"{int(chart.day_night_info['sunrise']):02d}:{int(round((chart.day_night_info['sunrise'] % 1) * 60)):02d}"
        if chart.day_night_info.get("sunset") is not None: sunset_utc = f"{int(chart.day_night_info['sunset']):02d}:{int(round((chart.day_night_info['sunset'] % 1) * 60)):02d}"
        
        major_positions_order = ['Ascendant', 'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn','Uranus', 'Neptune', 'Pluto', 'Chiron', 'True Node', 'South Node','Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)']
        
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
    except Exception as e:
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
