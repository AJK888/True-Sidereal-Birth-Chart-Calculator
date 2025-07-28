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
            # Data Payload for Unknown Time
            prompt_parts.append("\n**Anonymized Chart Data (Noon Calculation - Time-Sensitive Data Excluded):**")
            # This payload includes a 'percentage' key indicating how far through a sign a planet is.
            if sun: prompt_parts.append(f"- Sun: {sun['position']} ({sun['percentage']}%)")
            if moon: prompt_parts.append(f"- Moon: {moon['position']} ({moon['percentage']}%)")
            if s_analysis.get('dominant_element'): prompt_parts.append(f"- Dominant Element: {s_analysis.get('dominant_element')}")
            if numerology_analysis.get('life_path_number'): prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
            if numerology_analysis.get('day_number'): prompt_parts.append(f"- Day Number: {numerology_analysis.get('day_number')}")
            if numerology_analysis.get('name_numerology', {}).get('expression_number'): prompt_parts.append(f"- Expression Number: {numerology_analysis.get('name_numerology', {}).get('expression_number')}")
            if s_retrogrades:
                retro_list = ", ".join([p['name'] for p in s_retrogrades])
                prompt_parts.append(f"- Retrograde Planets: {retro_list}")
            if s_aspects:
                 prompt_parts.append(f"- Three Tightest Aspects: {s_aspects[0]['p1_name']} {s_aspects[0]['type']} {s_aspects[0]['p2_name']}, {s_aspects[1]['p1_name']} {s_aspects[1]['type']} {s_aspects[1]['p2_name']}, {s_aspects[2]['p1_name']} {s_aspects[2]['type']} {s_aspects[2]['p2_name']}")

            # Core Task for Unknown Time
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append(
                "Write an insightful narrative reading based *only* on the data provided.\n"
                "1.  **Internal Analysis:** First, silently identify the most powerful themes. Consider the dominant element, any sign stelliums, the Life Path and Day numbers, and the three tightest aspects. Notice if a planet is at a very early (0-5%) or late (95-100%) degree in a sign.\n"
                "2.  **Introduction:** Begin by introducing the single most powerful theme you discovered.\n"
                "3.  **Narrative:** Weave a story explaining this theme using the Sun, Moon, numerology, and the three tightest aspects as your evidence. Explain concepts simply as you go.\n"
                "4.  **Conclusion:** Summarize their key strengths, emphasizing that this is a powerful map of their inner world."
            )

        else:
            # --- PROMPT FOR KNOWN BIRTH TIME ---
            prompt_parts.append(
                "You are a wise, insightful, and deeply intuitive astrologer. Your special gift is synthesizing complex chart data into a cohesive and inspiring narrative for individuals who are new to astrology. You don't just list traits; you find the central story and overarching themes in a person's energetic blueprint and explain them with warmth and clarity."
            )
            
            # Full Data Payload
            prompt_parts.append("\n**Full Anonymized Chart Data:**")
            asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)
            # The 'percentage' key indicates how far a planet is through a sign. 0% is the beginning, 99% is the end.
            if sun: prompt_parts.append(f"- Sun: {sun['position']} ({sun['percentage']}%)")
            if moon: prompt_parts.append(f"- Moon: {moon['position']} ({moon['percentage']}%)")
            if asc: prompt_parts.append(f"- Ascendant: {asc['position']} ({asc['percentage']}%)")
            if s_analysis.get("chart_ruler"): prompt_parts.append(f"- Chart Ruler: {s_analysis['chart_ruler']}")
            if s_analysis.get("dominant_planet"): prompt_parts.append(f"- Dominant Planet: {s_analysis['dominant_planet']}")
            if s_analysis.get("dominant_sign"): prompt_parts.append(f"- Dominant Sign: {s_analysis['dominant_sign']}")
            if s_analysis.get("dominant_element"): prompt_parts.append(f"- Dominant Element: {s_analysis['dominant_element']}")
            
            prompt_parts.append("\n**Numerological & Other Data:**")
            if numerology_analysis.get("life_path_number"): prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
            if numerology_analysis.get("day_number"): prompt_parts.append(f"- Day Number: {numerology_analysis.get('day_number')}")
            if numerology_analysis.get("name_numerology"):
                name_nums = numerology_analysis['name_numerology']
                prompt_parts.append(f"- Expression Number: {name_nums.get('expression_number')}")
                prompt_parts.append(f"- Soul Urge Number: {name_nums.get('soul_urge_number')}")
                prompt_parts.append(f"- Personality Number: {name_nums.get('personality_number')}")
            if chinese_zodiac: prompt_parts.append(f"- Chinese Zodiac: {chinese_zodiac}")

            if s_patterns:
                prompt_parts.append("\n**Key Astrological Patterns (Stelliums):**")
                for pattern in s_patterns:
                    prompt_parts.append(f"- {pattern}")
            
            if s_retrogrades:
                prompt_parts.append("\n**Retrograde Planets (Energy turned inward for reflection):**")
                for planet in s_retrogrades:
                    prompt_parts.append(f"- {planet['name']}")

            if s_aspects:
                prompt_parts.append(f"\n**Three Tightest Aspects (Highest Influence):**")
                for aspect in s_aspects[:3]:
                    prompt_parts.append(f"- {aspect['p1_name']} {aspect['type']} {aspect['p2_name']} (Orb: {aspect['orb']})")

            # Full Core Task
            prompt_parts.append("\n**Your Task:**")
            prompt_parts.append("""
**Step 1: Internal Analysis (Do this silently before writing)**
First, perform a deep, holistic review of ALL the data provided to find the chart's core narrative.
1.  **Generate a List of 10 Potential Themes:** Look for powerful, repeating patterns. Consider:
    * All **stelliums** (both sign and house). A 9th house stellium points to higher learning. A Leo stellium points to creative expression.
    * The **Life Path Number** and **Day Number**. A Life Path 7 is the seeker. A Day Number 8 points to ambition and power.
    * The **Chart Ruler**'s sign and house placement. This reveals the "captain" of the life direction.
    * The **Dominant Element** and **Planet**. Fire dominance shows passion; Saturn dominance shows discipline.
    * **Planet Degree Percentages**. A planet at 0-5% is new to its energy; one at 95-99% is mastering or graduating from it.
    * The meaning of the **three tightest aspects**. A Sun-Pluto square is a theme of power and transformation.
2.  **Select the Primary Narrative:** From your list of 10, identify the **1 or 2 most powerful and interconnected themes**. This will be the central story you tell. For example, a 9th house stellium + Life Path 7 + Sagittarius dominance is a single, powerful theme of 'The Lifelong Seeker'.
""")

            prompt_parts.append("""
**Step 2: Write the Narrative Reading**
Now, write a detailed, multi-paragraph reading for the beginner. **Do not follow a rigid template.** Craft a flowing narrative built around the primary theme you selected.

-   **Introduction - The Central Theme:** Begin by introducing the powerful, central story you discovered.
-   **Body - Weaving the Evidence:** In the following paragraphs, explain this theme using the specific placements you identified as your evidence.
    -   **Integrate Everything:** You must weave in **all stelliums**, the **Life Path and Day Numbers**, and the **three tightest aspects** into your narrative. Show how they support or add complexity to the central theme.
    -   **Explain Concepts As You Go:** As you introduce each component (like the Sun, a House, or a stellium), briefly explain its role in simple, relatable terms.
    -   **Use Planet Degrees:** Mention if a key planet is at the beginning or end of a sign and what that might mean (e.g., 'Your Sun is at the very end of Leo, suggesting a lifetime spent mastering the art of creative expression...').
-   **Conclusion - The Empowering Summary:** Conclude with a warm summary of their unique energetic toolkit, framing it as a map for their life's journey.
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
