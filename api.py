# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart,
    calculate_numerology, get_chinese_zodiac_and_element,
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

# In api.py

async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    """
    Generates a Gemini reading. Switches between a full reading (known time)
    and a limited, planets-only reading (unknown time).
    """
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    try:
        # --- Data Extraction (common to both prompts) ---
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        chinese_zodiac = chart_data.get("chinese_zodiac")
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        s_patterns = chart_data.get("sidereal_aspect_patterns", [])
        s_retrogrades = chart_data.get("sidereal_retrogrades", [])
        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)

        prompt_parts = []

        if unknown_time:
            # --- PROMPT FOR UNKNOWN BIRTH TIME ---
            prompt_parts.append(
                "You are a wise astrologer providing a reading for a chart where the exact birth time is unknown. "
                "This is called a 'Noon Chart'.\n"
                "**Your most important rule is to completely avoid mentioning the Ascendant, Midheaven (MC), Chart Ruler, or any House placements, as they are unknown and cannot be used.** "
                "You must focus exclusively on the placement of planets in their signs, the aspects between them, and the numerology."
            )
            # Data Payload for Unknown Time...
            
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
First, perform a silent internal analysis to identify the most powerful themes from the limited data. Then, structure your final response exactly as follows, using the specified markdown headers:

### Key Themes in Your Chart
(List the 2-3 most important themes you can identify from the data.)

### The Story of Your Inner World
(Write a multi-paragraph narrative weaving together the Sun, Moon, numerology, and the three tightest aspects to explain the core themes.)
""")

        else:
            # --- PROMPT FOR KNOWN BIRTH TIME ---
            prompt_parts.append(
                "You are a wise, insightful, and deeply intuitive astrologer. Your special gift is synthesizing complex chart data into a cohesive and inspiring narrative for individuals who are new to astrology. You don't just list traits; you find the central story and overarching themes in a person's energetic blueprint and explain them with warmth and clarity."
            )
            
            # Full Data Payload...
            
            # --- The Core Task with New Formatting Instructions ---
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
**Step 1: Internal Analysis (Do this silently before writing)**
First, perform a deep, holistic review of ALL the data provided to find the chart's core narrative.
1.  **Generate a List of 10 Potential Themes:** Look for powerful, repeating patterns. Consider:
    * All **stelliums** (both sign and house).
    * The **Life Path Number** and **Day Number**.
    * The **Chart Ruler**'s sign and house placement.
    * The **Dominant Element** and **Planet**.
    * **Planet Degree Percentages**. A planet at 0-5% is new to its energy; one at 95-99% is mastering it.
    * The meaning of the **three tightest aspects**.
2.  **Select the Primary Narrative:** From your list of 10, identify the **1 or 2 most powerful and interconnected themes**. This will be the central story you tell.
""")

            prompt_parts.append("""
**Step 2: Write the Final Reading**
Now, write the final reading for the user. Structure your entire response **exactly as follows**, using the markdown headings as specified. Do not include headers like "Step 1", "Step 2", or "Primary Narrative".

### Key Themes in Your Chart
(Under this heading, list the 3 to 5 most important and interconnected themes you identified from your internal analysis. Be concise.)

### The Central Story of Your Chart
(Under this heading, write the full, multi-paragraph narrative reading. This is where you will weave together all the evidence (all stelliums, numerology numbers, the three tightest aspects, etc.) to tell the cohesive story of the chart, built around the primary theme you selected. Explain concepts simply as you go.)
""")

        prompt = "\n".join(prompt_parts)

        # --- API Call ---
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt)
        
        # Clean up the response to ensure it starts with the correct header
        cleaned_response = response.text.strip()
        if "### Key Themes in Your Chart" not in cleaned_response:
             # Fallback if the model doesn't follow instructions perfectly
             return cleaned_response
        
        return cleaned_response
        
    except Exception as e:
        logger.error(f"Error during Gemini reading generation: {e}", exc_info=True)
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
        chinese_zodiac = get_chinese_zodiac_and_element(data.year, data.month, data.day)
        
        full_response = chart.get_full_chart_data(numerology, name_numerology, chinese_zodiac, data.unknown_time)
        
        # <-- FIX: Pass the 'data.unknown_time' boolean here
        gemini_reading = await get_gemini_reading(full_response, data.unknown_time)
        full_response["gemini_reading"] = gemini_reading

        return full_response

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
