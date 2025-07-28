# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from natal_chart import (
    NatalChart, get_sign_and_ruler, format_true_sidereal_placement, PLANETS_CONFIG, 
    # FIX: The function name is updated here
    calculate_numerology, get_chinese_zodiac_and_element, TRUE_SIDEREAL_SIGNS,
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
    # "http://127.0.0.1:5500" # Example for local testing
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
        # --- Prompt Engineering ---
        prompt_parts = [
            # 1. The System Role: Framed as a storyteller and synthesist.
            "You are a wise, insightful, and deeply intuitive astrologer. Your special gift is synthesizing complex chart data into a cohesive and inspiring narrative for individuals who are new to astrology. You don't just list traits; you find the central story and overarching themes in a person's energetic blueprint and explain them with warmth and clarity.",
        ]

        # 2. Append all the anonymized data for context
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        chinese_zodiac = chart_data.get("chinese_zodiac")
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        s_patterns = chart_data.get("sidereal_aspect_patterns", [])

        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)
        asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)

        prompt_parts.append("\n**Full Anonymized Chart Data:**")
        prompt_parts.append("**Astrological Data:**")
        if sun: prompt_parts.append(f"- Sun: {sun['position']}")
        if moon: prompt_parts.append(f"- Moon: {moon['position']}")
        if asc: prompt_parts.append(f"- Ascendant: {asc['position']}")
        if s_analysis.get("chart_ruler"): prompt_parts.append(f"- Chart Ruler: {s_analysis['chart_ruler']}")
        if s_analysis.get("dominant_planet"): prompt_parts.append(f"- Dominant Planet: {s_analysis['dominant_planet']}")
        if s_analysis.get("dominant_sign"): prompt_parts.append(f"- Dominant Sign: {s_analysis['dominant_sign']}")
        if s_analysis.get("dominant_element"): prompt_parts.append(f"- Dominant Element: {s_analysis['dominant_element']}")
        
        prompt_parts.append("\n**Numerological & Other Data:**")
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
        
        top_aspects = s_aspects[:20] # Provide more aspects for better context
        if top_aspects:
            prompt_parts.append("\n**Major Aspects:**")
            for aspect in top_aspects:
                prompt_parts.append(f"- {aspect['p1_name']} {aspect['type']} {aspect['p2_name']}")
        
        # 3. The Core Task: The new, advanced instructions
        prompt_parts.append("\n**Your Task:**")
        prompt_parts.append("""
**Step 1: Internal Analysis (Do this silently before writing)**
First, review ALL the data provided above. Look for the most powerful, repeating themes and patterns that form the 'center of gravity' of this chart.
-   Is there a powerful **Stellium** (concentration of planets) in a specific house or sign?
-   Do the **Numerology** numbers (like a Life Path 7 and Soul Urge 7) strongly echo the themes of a planet or house?
-   Does the **Chart Ruler**, **Dominant Planet**, or **Dominant Element** create an undeniable theme?
-   Look for powerful combinations. For example, a 9th House Stellium + Life Path 7 is a massive theme of spiritual seeking and higher knowledge. A stellium in Libra + a Venus-ruled chart + an Expression Number 6 is a powerful theme of relationships, art, and harmony.
-   Identify 1-2 of these most powerful, overarching themes. You will build your entire narrative around them.
""")

        prompt_parts.append("""
**Step 2: Write the Narrative Reading**
Now, write a detailed, multi-paragraph reading for the beginner. **Do not follow a rigid template.** Instead, craft a flowing narrative based on the core themes you identified in your internal analysis.

-   **Introduction - The Central Theme:** Begin by introducing the most powerful theme you discovered. Open with a statement that captures the essence of their chart, such as, "Your chart tells a powerful story about a journey of..." or "If we look at your cosmic blueprint, the central theme that shines brightest is one of..."

-   **Body - Weaving the Evidence:** In the following paragraphs, explain this central theme using the specific astrological and numerological placements as your evidence. Instead of listing them one by one, group them by how they support the narrative.
    -   **Explain Concepts As You Go:** As you introduce each component (like the Sun, a House, or an Aspect) for the first time, briefly explain its role in simple, relatable terms.
    -   **Example of Weaving:** If the theme is "Creative Self-Expression," you might say: "This theme of creativity is anchored by your Sun, which represents your core identity, shining brightly in the dramatic sign of Leo. This tells us you're meant to be on a stage, whether literally or figuratively. This is powerfully amplified by a concentration of planets in your 5th House—the area of your chart connected to creativity and play. The fact that your Expression Number from numerology is a 3, the number of communication and artistry, confirms that this is not just a hobby, but a core part of your purpose."

-   **Complexity and Growth - The Aspects:** Weave in the meaning of one or two key **aspects** (the conversations between planets). Explain how they add harmony or dynamic tension to the core themes you're describing. For instance, "...while your creative drive is strong, it might face a challenge from Saturn, the planet of discipline. This tension isn't a weakness; it's a cosmic personal trainer, pushing you to build real, lasting structures for your art."

-   **Conclusion - The Empowering Summary:** Conclude with a warm summary. Reiterate their core strengths and potential, framing their chart not as a fixed destiny, but as a beautiful and powerful toolkit they've been given for their life's journey.
""")

        prompt = "\n".join(prompt_parts)

        # --- API Call ---
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt)
        
        return response.text
        
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

        # 1. Instantiate and calculate the chart
        chart = NatalChart(
            name=data.full_name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng
        )
        chart.calculate_chart()
        
        # 2. Perform other calculations
        numerology = calculate_numerology(data.day, data.month, data.year)
        name_numerology = calculate_name_numerology(data.full_name)
        chinese_zodiac = get_chinese_zodiac_and_element(data.year, data.month, data.day)
        
        # 3. Get the formatted response dictionary from the chart object
        full_response = chart.get_full_chart_data(numerology, name_numerology, chinese_zodiac, data.unknown_time)
        
        # 4. If time is known, get the AI reading
        if not data.unknown_time:
            gemini_reading = await get_gemini_reading(full_response)
            full_response["gemini_reading"] = gemini_reading

        return full_response

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")
