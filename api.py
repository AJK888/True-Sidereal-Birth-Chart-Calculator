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
        # Data Extraction (common to both prompts)
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
            # PROMPT FOR UNKNOWN BIRTH TIME
            prompt_parts.append(
                "You are a wise astrologer providing a reading for a chart where the exact birth time is unknown. "
                "This is called a 'Noon Chart'.\n"
                "**Your most important rule is to completely avoid mentioning the Ascendant, Midheaven (MC), Chart Ruler, or any House placements, as they are unknown and cannot be used.** "
                "You must focus exclusively on the placement of planets in their signs, the aspects between them, and the numerology."
            )
            prompt_parts.append("\n**Anonymized Chart Data (Noon Calculation - Time-Sensitive Data Excluded):**")
            if sun: prompt_parts.append(f"- Sun: {sun['position']}")
            if moon: prompt_parts.append(f"- Moon: {moon['position']}")
            if s_analysis.get('dominant_element'): prompt_parts.append(f"- Dominant Element: {s_analysis.get('dominant_element')}")
            if numerology_analysis.get('life_path_number'): prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
            if numerology_analysis.get('name_numerology', {}).get('expression_number'): prompt_parts.append(f"- Expression Number: {numerology_analysis.get('name_numerology', {}).get('expression_number')}")
            if s_retrogrades:
                retro_list = ", ".join([p['name'] for p in s_retrogrades])
                prompt_parts.append(f"- Retrograde Planets: {retro_list}")
            
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append(
                "Write a slightly shorter but insightful narrative reading based *only* on the data provided.\n"
                "1.  **Introduction:** Start by explaining that this reading is based on a snapshot of the planets on their birthday, revealing their core personality drivers.\n"
                "2.  **The Core Self:** Discuss the **Sun** (their fundamental identity) and the **Moon** (their inner emotional world) as the two main characters of their story.\n"
                "3.  **Personality Flavor:** Weave in the meaning of the **dominant element** and a few other key planets in their signs to describe their overall energy and style.\n"
                "4.  **Life's Journey:** Incorporate their **Life Path and Expression Numbers** to talk about their natural talents and the path they are here to walk.\n"
                "5.  **Conclusion:** Summarize their key strengths, emphasizing that this is a powerful map of their inner world, even without the birth time."
            )

        else:
            # PROMPT FOR KNOWN BIRTH TIME
            prompt_parts.append(
                "You are a wise, insightful, and deeply intuitive astrologer. Your special gift is synthesizing complex chart data into a cohesive and inspiring narrative for individuals who are new to astrology. You don't just list traits; you find the central story and overarching themes in a person's energetic blueprint and explain them with warmth and clarity."
            )
            prompt_parts.append("\n**Full Anonymized Chart Data:**")
            asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)
            if sun: prompt_parts.append(f"- Sun: {sun['position']}")
            if moon: prompt_parts.append(f"- Moon: {moon['position']}")
            if asc: prompt_parts.append(f"- Ascendant: {asc['position']}")
            if s_analysis.get("chart_ruler"): prompt_parts.append(f"- Chart Ruler: {s_analysis['chart_ruler']}")
            if s_analysis.get("dominant_planet"): prompt_parts.append(f"- Dominant Planet: {s_analysis['dominant_planet']}")
            if s_analysis.get("dominant_sign"): prompt_parts.append(f"- Dominant Sign: {s_analysis['dominant_sign']}")
            if s_analysis.get("dominant_element"): prompt_parts.append(f"- Dominant Element: {s_analysis['dominant_element']}")
            
            prompt_parts.append("\n**Numerological & Other Data:**")
            if numerology_analysis.get("life_path_number"): prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
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
            
            if s_retrogrades:
                prompt_parts.append("\n**Retrograde Planets (Energy turned inward for reflection):**")
                for planet in s_retrogrades:
                    prompt_parts.append(f"- {planet['name']}")

            top_aspects = s_aspects[:20]
            if top_aspects:
                prompt_parts.append("\n**Major Aspects:**")
                for aspect in top_aspects:
                    prompt_parts.append(f"- {aspect['p1_name']} {aspect['type']} {aspect['p2_name']}")
            
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
**Step 1: Internal Analysis (Do this silently before writing)**
First, review ALL the data provided above. Look for the most powerful, repeating themes and patterns that form the 'center of gravity' of this chart.
-   Identify 1-2 of these most powerful, overarching themes. You will build your entire narrative around them.
""")

            prompt_parts.append("""
**Step 2: Write the Narrative Reading**
Now, write a detailed, multi-paragraph reading for the beginner. **Do not follow a rigid template.** Instead, craft a flowing narrative based on the core themes you identified.

-   **Introduction - The Central Theme:** Begin by introducing the most powerful theme you discovered.
-   **Body - Weaving the Evidence:** Explain this central theme using the specific placements as evidence.
    -   **Explain Concepts As You Go:** As you introduce each component (like the Sun or an Aspect), briefly explain its role in simple terms.
    -   **The Chart's Guide - The Ruler:** Make sure to mention the **Chart Ruler** and explain it as the 'captain of the ship'.
    -   **Inward Energy - Retrogrades:** If there are retrograde planets, explain this concept simply as the planet's energy being turned inward.
-   **Complexity and Growth - The Aspects:** Weave in the meaning of one or two key **aspects**.
-   **Conclusion - The Empowering Summary:** Conclude with a warm, empowering summary.
""")

        prompt = "\n".join(prompt_parts)

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
