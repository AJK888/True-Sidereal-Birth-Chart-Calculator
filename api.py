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

async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    """
    Generates a Gemini reading. Switches between a full reading (known time)
    and a limited, planets-only reading (unknown time).
    """
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    try:
        # --- Data Extraction (remains the same) ---
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
            # --- PROMPT FOR UNKNOWN BIRTH TIME (Corrected) ---
            prompt_parts.append(
                "You are a wise astrologer providing a reading for a chart where the exact birth time is unknown. "
                "Your most important rule is to completely avoid mentioning the Ascendant, Midheaven (MC), Chart Ruler, or any House placements, as they are unknown and cannot be used. "
                "Your goal is to find the central story told by the planets, signs, aspects, and numerology alone."
            )
            # Data Payload for Unknown Time... (code to append data is the same)
            
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
1.  **Internal Analysis:** First, silently analyze the user's actual chart data provided. Identify the most powerful themes by considering the dominant element, any sign stelliums, the Life Path and Day numbers, and the three tightest aspects. Notice if a planet is at a very early or late degree.
2.  **Write the Narrative:** Craft a flowing narrative built around the central theme you discover from the user's data. You MUST integrate the meaning of the **Life Path and Day Numbers** and the **three tightest aspects**. Show how they all tell the same core story from different angles.
3.  **Explain Concepts:** Briefly explain astrological terms (like the Sun, Moon, an aspect) as you introduce them.
4.  **Structure:** Start with an introduction to the central theme, develop it in the body paragraphs by showing how the data points connect, and conclude with an empowering summary.
""")

        else:
            # --- PROMPT FOR KNOWN BIRTH TIME (Corrected) ---
            prompt_parts.append(
                "You are a master astrologer and esoteric synthesist. Your clients come to you for readings of unparalleled depth. Your unique skill is identifying the 'golden thread'—the central narrative or soul's purpose—that connects every single placement, aspect, and number in a person's blueprint. You see the chart not as a collection of parts, but as a single, cohesive, living story."
            )
            
            # Full Data Payload (code to append data is the same)...
            
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
**Step 1: Internal Analysis (Do this silently before writing, using ONLY the user's real chart data)**
First, perform a deep, holistic review of ALL the data provided for the user to find the chart's core narrative.
1.  **Generate a List of Potential Themes:** Brainstorm a comprehensive list of major themes based on the user's data. Look for powerful, repeating patterns. Consider:
    * All **stelliums** (both sign and house).
    * The **Life Path Number** and **Day Number**.
    * The **Chart Ruler**'s sign and house placement.
    * The **Dominant Element** and **Planet**.
    * **Planet Degree Percentages**.
    * The meaning of the **three tightest aspects**.
2.  **Group the Evidence:** For the top themes, internally group the specific chart placements and numbers that support each theme. This is to force you to see the connections within the user's actual chart.
3.  **Select the Primary Narrative:** From your analysis, identify the **single most compelling and interconnected theme** in the user's chart. This will be the 'golden thread' of your reading.
""")

            prompt_parts.append("""
**Step 2: Write the Final Reading**
Now, write the final reading for the user. Structure your entire response **exactly as follows**, using the markdown headings as specified. Do not include headers like "Step 1", "Step 2", or "Primary Narrative".

### Key Themes in Your Chart
(Under this heading, list the 3 to 5 most important and interconnected themes you identified from your internal analysis of the user's chart. Be concise.)

### The Central Story of Your Chart
(Under this heading, write the full, multi-paragraph narrative reading. Your primary goal here is to **demonstrate how different parts of the user's chart tell the SAME story from different angles.** Avoid discussing any placement in isolation.)

-   **Introduction - The Golden Thread:** Begin by stating the central, unifying theme you discovered in the user's chart. Present it as the 'golden thread' or the 'soul's mission statement' for this lifetime.
-   **Body - The Unfolding Narrative:** Dedicate each paragraph to exploring a facet of the central theme.
    -   **MANDATORY INTEGRATION:** You **must not** have a separate 'numerology paragraph' or 'aspect paragraph.' Instead, when you discuss the user's life purpose (e.g., the Sun), you MUST connect it to their Life Path Number. When you discuss a key challenge (a hard aspect), you MUST connect it to the house it's in and how it affects the overall theme.
    -   **Make connections explicit.** For example, your explanation should follow this logic: 'Your core identity, represented by your Sun's placement, is fundamentally about X. This is the very mission statement of your soul, which is perfectly echoed by your Life Path Number Y, the number of Z.'
    -   You are required to seamlessly integrate the meaning of **all stelliums**, the **Chart Ruler**, the **Life Path and Day Numbers**, and the **three tightest aspects** into this single, flowing narrative.
-   **Conclusion - The Tapestry:** Conclude with a summary that presents the user's chart as a beautiful, intricate tapestry. Reiterate that the challenges and strengths are all part of one unified design, perfectly equipping them for their unique purpose.
""")

        prompt = "\n".join(prompt_parts)

        # --- API Call ---
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt)
        
        cleaned_response = response.text.strip()
        
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
