from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from natal_chart import (
    NatalChart,
    calculate_numerology, get_chinese_zodiac_and_element,
    calculate_name_numerology,
    TRUE_SIDEREAL_SIGNS
)
import swisseph as swe
import traceback
import requests
import pendulum
import os
import logging
from logtail import LogtailHandler
import google.generativeai as genai
import asyncio
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import uuid

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

# --- Admin Secret Key for bypassing rate limit ---
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

# --- Rate Limiter Key Function ---
def get_rate_limit_key(request: Request) -> str:
    if ADMIN_SECRET_KEY:
        admin_secret_header = request.headers.get("x-admin-secret")
        if admin_secret_header and admin_secret_header == ADMIN_SECRET_KEY:
            return str(uuid.uuid4())
    return get_remote_address(request)


# --- SETUP FASTAPI APP & RATE LIMITER ---
limiter = Limiter(key_func=get_rate_limit_key)
app = FastAPI(title="True Sidereal API", version="1.0")
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Thank you for using Synthesis Astrology. Due to high API costs we limit user's requests for readings. Please reach out to the developer if you would like them to provide you a reading."}
    )

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"message": "ok"}

# --- CORS MIDDLEWARE ---
origins = [
    "https://synthesisastrology.org",
    "https://www.synthesisastrology.org",
    "https://synthesisastrology.com",
    "https://www.synthesisastrology.com",
    "https://true-sidereal-birth-chart.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class ChartRequest(BaseModel):
    full_name: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    location: str
    unknown_time: bool = False
    user_email: Optional[str] = None # Kept for data collection, but not used for sending email
    no_full_name: bool = False

class ReadingRequest(BaseModel):
    chart_data: Dict[str, Any]
    unknown_time: bool
    user_inputs: Dict[str, Any]
    chart_image_base64: Optional[str] = None


# --- AI Reading Functions ---

async def _run_gemini_prompt(prompt_text: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = await model.generate_content_async(prompt_text)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in Gemini API call: {e}", exc_info=True)
        return f"An error occurred during a Gemini API call: {e}"

async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    if unknown_time:
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        s_retrogrades = chart_data.get("sidereal_retrogrades", [])
        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)
        
        prompt_parts = [
            "You are a wise astrologer providing a reading for a chart where the exact birth time is unknown. "
            "This is called a 'Noon Chart'.\n"
            "**Your most important rule is to completely avoid mentioning the Ascendant, Midheaven (MC), Chart Ruler, or any House placements, as they are unknown and cannot be used.** "
            "You must focus exclusively on the placement of planets in their signs, the aspects between them, and the numerology.",
            "\n**Anonymized Chart Data (Noon Calculation - Time-Sensitive Data Excluded):**"
        ]
        if sun: prompt_parts.append(f"- Sun: {sun['position']} ({sun['percentage']}%)")
        if moon: prompt_parts.append(f"- Moon: {moon['position']} ({moon['percentage']}%)")
        if s_analysis.get('dominant_element'): prompt_parts.append(f"- Dominant Element: {s_analysis.get('dominant_element')}")
        if numerology_analysis.get('life_path_number'): prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
        if numerology_analysis.get('day_number'): prompt_parts.append(f"- Day Number: {numerology_analysis.get('day_number')}")
        if numerology_analysis.get('name_numerology', {}).get('expression_number'): prompt_parts.append(f"- Expression Number: {numerology_analysis.get('name_numerology', {}).get('expression_number')}")
        if s_retrogrades:
            retro_list = ", ".join([p['name'] for p in s_retrogrades])
            prompt_parts.append(f"- Retrograde Planets: {retro_list}")
        if s_aspects and len(s_aspects) >= 3:
            prompt_parts.append(f"- Three Tightest Aspects: {s_aspects[0]['p1_name']} {s_aspects[0]['type']} {s_aspects[0]['p2_name']}, {s_aspects[1]['p1_name']} {s_aspects[1]['type']} {s_aspects[1]['p2_name']}, {s_aspects[2]['p1_name']} {s_aspects[2]['type']} {s_aspects[2]['p2_name']}")

        prompt_parts.append("\n**Your Task:**")
        prompt_parts.append("""
First, perform a silent internal analysis to identify the most powerful themes from the limited data. Then, structure your final response **exactly as follows, using plain text without any markdown like '#' or '**'.**

Key Themes in Your Chart
(Under this plain text heading, list the 2-3 most important themes you identified.)

The Story of Your Inner World
(Under this plain text heading, write a multi-paragraph narrative weaving together the Sun, Moon, numerology, and the three tightest aspects to explain the core themes. Do not use sub-labels like 'Introduction' or 'Body'.)
""")
        return await _run_gemini_prompt("\n".join(prompt_parts))

    try:
        # Step 1: Analyze Alignments
        cartographer_data = []
        s_pos = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
        t_pos = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
        for body in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Ascendant']:
            if body in s_pos and body in t_pos:
                cartographer_data.append(f"- {body}: Sidereal {s_pos[body]['position'].split(' ')[-1]}, Tropical {t_pos[body]['position'].split(' ')[-1]}")
        
        cartographer_prompt = f"""
Analyze the provided Sidereal and Tropical placements to identify the primary points of alignment, tension, and contrast. Do not interpret the meaning. Your output must be a simple, structured list.

**Data to Analyze:**
{'/n'.join(cartographer_data)}

**Your Task:**
1. For each body, state the relationship between its Sidereal and Tropical sign placements.
2. Label each finding with one of the following classifications: "High Alignment" (same sign), "Moderate Tension" (adjacent signs), or "High Contrast" (signs in different elements/modalities).
3. Output nothing but this list.
"""
        cartographer_analysis = await _run_gemini_prompt(cartographer_prompt)

        # Step 2: Identify Foundational Blueprint
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        t_analysis = chart_data.get("tropical_chart_analysis", {})
        numerology = chart_data.get("numerology_analysis", {})
        architect_data = [
            f"- Sidereal Sun: {s_pos.get('Sun', {}).get('position')} in House {s_pos.get('Sun', {}).get('house_num')}",
            f"- Tropical Sun: {t_pos.get('Sun', {}).get('position')} in House {t_pos.get('Sun', {}).get('house_num')}",
            f"- Sidereal Moon: {s_pos.get('Moon', {}).get('position')} in House {s_pos.get('Moon', {}).get('house_num')}",
            f"- Tropical Moon: {t_pos.get('Moon', {}).get('position')} in House {t_pos.get('Moon', {}).get('house_num')}",
            f"- Sidereal Ascendant: {s_pos.get('Ascendant', {}).get('position')}",
            f"- Tropical Ascendant: {t_pos.get('Ascendant', {}).get('position')}",
            f"- Chart Ruler: {s_analysis.get('chart_ruler')}",
            f"- Dominant Planet (Sidereal): {s_analysis.get('dominant_planet')}",
            f"- Dominant Planet (Tropical): {t_analysis.get('dominant_planet')}",
            f"- Life Path Number: {numerology.get('life_path_number')}",
            f"- Day Number: {numerology.get('day_number')}",
            f"- Chinese Zodiac: {chart_data.get('chinese_zodiac')}"
        ]
        architect_prompt = f"""
Identify the foundational blueprint of a soul. Analyze the provided chart data and the alignment map to determine the 3-5 central themes of this person's life.

**Zodiac Definitions:**
- The **Sidereal** placements represent the soul's deeper karmic blueprint, innate spiritual gifts, and ultimate life purpose.
- The **Tropical** placements represent the personality's expression, psychological patterns, and how the soul's purpose manifests in this lifetime.

**Alignment Analysis:**
{cartographer_analysis}

**Core Chart Data:**
{'/n'.join(architect_data)}

**Your Task:**
1. Review all provided data.
2. Identify the 3-5 most powerful and interconnected themes that define the core of this chart.
3. For each theme, list the specific Sidereal, Tropical, and Numerological/Zodiacal data points that serve as evidence.
4. Output this as a structured list. Do not write a narrative.
"""
        architect_analysis = await _run_gemini_prompt(architect_prompt)

        # Step 3: Interpret Karmic Path
        s_south_node = s_pos.get('South Node', {})
        s_north_node = s_pos.get('True Node', {})
        t_south_node = t_pos.get('South Node', {})
        t_north_node = t_pos.get('True Node', {})
        
        navigator_data = [
            f"- Sidereal South Node: {s_south_node.get('position')} in House {s_south_node.get('house_num')}",
            f"- Sidereal North Node: {s_north_node.get('position')} in House {s_north_node.get('house_num')}",
            f"- Tropical South Node: {t_south_node.get('position')} in House {t_south_node.get('house_num')}",
            f"- Tropical North Node: {t_north_node.get('position')} in House {t_north_node.get('house_num')}",
            f"- Dominant Element: {s_analysis.get('dominant_element')}"
        ]
        navigator_prompt = f"""
Interpret the soul's journey from its past to its future potential, based on the Nodal Axis. Use the provided foundational themes to guide your interpretation.

**Foundational Themes:**
{architect_analysis}

**Nodal Axis Data:**
{'/n'.join(navigator_data)}

**Your Task:**
1.  **Interpret the South Node:** Describe the past-life comfort zones, karmic patterns, and innate gifts represented by the South Node's position in both zodiacs.
2.  **Interpret the North Node:** Describe the soul's mission, growth potential, and the qualities it must develop in this lifetime, as shown by the North Node's position in both zodiacs.
3.  **Synthesize:** In a concluding paragraph, explain how the Sidereal (soul path) and Tropical (personality expression) Nodal placements work together. In your synthesis, highlight how the nodal axis is supported or challenged by the chart's dominant element and any aspect patterns involving the nodes.
"""
        navigator_analysis = await _run_gemini_prompt(navigator_prompt)

        # Step 4: Perform Deep-Dive Planetary Analysis (Concurrent Calls)
        async def run_specialist_for_planet(planet_name):
            s_planet = s_pos.get(planet_name, {})
            t_planet = t_pos.get(planet_name, {})
            
            def format_aspect_string(aspect, planet_positions):
                p1_name = aspect['p1_name'].split(' in ')[0]
                p2_name = aspect['p2_name'].split(' in ')[0]
                p1_details = planet_positions.get(p1_name, {})
                p2_details = planet_positions.get(p2_name, {})
                return f"{aspect['p1_name']} in House {p1_details.get('house_num')} {aspect['type']} {aspect['p2_name']} in House {p2_details.get('house_num')} ({aspect['orb']} orb)"

            all_s_aspects = chart_data.get('sidereal_aspects', [])
            planet_s_aspects = sorted([a for a in all_s_aspects if planet_name in a['p1_name'] or planet_name in a['p2_name']], key=lambda x: float(x['orb'][:-1]))[:2]
            s_aspects_text = [format_aspect_string(a, s_pos) for a in planet_s_aspects]

            all_t_aspects = chart_data.get('tropical_aspects', [])
            planet_t_aspects = sorted([a for a in all_t_aspects if planet_name in a['p1_name'] or planet_name in a['p2_name']], key=lambda x: float(x['orb'][:-1]))[:2]
            t_aspects_text = [format_aspect_string(a, t_pos) for a in planet_t_aspects]

            specialist_data = [
                f"- Sidereal Placement: {s_planet.get('position')} in House {s_planet.get('house_num')}",
                f"- Tropical Placement: {t_planet.get('position')} in House {t_planet.get('house_num')}",
                f"- Retrograde Status: {'Yes' if s_planet.get('retrograde') else 'No'}",
                f"- Sidereal Aspects: {', '.join(s_aspects_text)}",
                f"- Tropical Aspects: {', '.join(t_aspects_text)}"
            ]
            
            specialist_prompt = f"""
For the planet {planet_name}, you must write four separate, detailed paragraphs: one for its Sidereal interpretation, one for its Tropical interpretation, a third for synthesizing these views, and a fourth analyzing its two tightest aspects. Use precise astrological terminology and explain your reasoning—not just conclusions.

**Foundational Themes:**
{architect_analysis}

**{planet_name} Data:**
{'/n'.join(specialist_data)}

**Your Task:**
Write four clearly separated, detailed paragraphs:

**Sidereal Interpretation:**
(In this paragraph, explain the soul’s core essence and karmic purpose related to {planet_name}. You MUST provide a deep analysis of its placement in its **sign AND house**. Explain the psychological implications of the house placement. Also discuss element, modality, rulership, and dignity/debility. If Retrograde Status is 'Yes', explain the full impact of its internalized energy and revisited themes.)

**Tropical Interpretation:**
(In this paragraph, explain how the soul’s purpose is expressed through the personality via {planet_name}. You MUST provide a deep analysis of its placement in its **sign AND house**. Explain how the house placement affects its behavioral expression and how it modifies or amplifies the Sidereal placement.)

**Synthesis:**
(In this paragraph, compare the Sidereal vs. Tropical expressions. Are they aligned, in tension, or complementary? How does the house placement in one system support or challenge the other?)

**Aspect Analysis:**
(In this paragraph, explain the two tightest aspects involving this planet. For each aspect, you must state the full aspect string provided in the data, like: "Mercury square Saturn (2.4° orb) from Leo in the 1st House to Aries in the 6th House introduces tension between…". Provide a detailed interpretation of each aspect's influence.)
"""
            return f"--- ANALYSIS FOR {planet_name.upper()} ---\n{await _run_gemini_prompt(specialist_prompt)}"

        planets_to_analyze = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        specialist_tasks = [run_specialist_for_planet(p) for p in planets_to_analyze]
        specialist_analyses = await asyncio.gather(*specialist_tasks)
        combined_specialist_analysis = "\n\n".join(specialist_analyses)

        # Step 5: Analyze Chart Dynamics
        weaver_data = [p.get('description', '') for p in chart_data.get('sidereal_aspect_patterns', [])]
        s_tightest_aspects = chart_data.get('sidereal_aspects', [])[:3]
        
        weaver_prompt = f"""
Synthesize the individual planetary analyses by interpreting the major aspect patterns and the three tightest aspects in the chart overall.

**Planetary Analyses:**
{combined_specialist_analysis}

**Chart Pattern Data:**
- Patterns: {', '.join(weaver_data)}
- Tightest Aspects: {[f"{a['p1_name']} {a['type']} {a['p2_name']}" for a in s_tightest_aspects]}

**Your Task:**
1.  **Analyze Tightest Aspects:** For each of the three tightest aspects provided, write a dedicated, detailed paragraph. Explain the dynamic it creates between the two planets involved, referencing their signs and houses from the planetary analyses. Describe how this energy is likely to manifest as a core life theme, representing a central challenge or strength for the individual.
2.  **Analyze Chart Patterns:** For each listed chart pattern (e.g., T-Square, Stellium), write a paragraph explaining its dynamic. How does it integrate the energies of the involved planets? Refer back to the provided planetary analyses to enrich your interpretation.
"""
        weaver_analysis = await _run_gemini_prompt(weaver_prompt)

        # Step 6: Final Synthesis
        storyteller_prompt = f"""
You are an insightful astrological consultant who excels at weaving complex data into a clear and compelling narrative. Your skill is in explaining complex astrological data in a practical and grounded way. You will write a comprehensive, in-depth reading based *exclusively* on the structured analysis provided below. Your tone should be insightful and helpful, avoiding overly spiritual or "dreamy" language.

**CRITICAL RULE:** Base your reading *only* on the analysis provided. Do not invent any placements, planets, signs, or aspects that are not explicitly listed in the analysis.

**Provided Analysis:**
---
**ALIGNMENT MAP:**
{cartographer_analysis}
---
**FOUNDATIONAL THEMES:**
{architect_analysis}
---
**KARMIC PATH:**
{navigator_analysis}
---
**PLANETARY DEEP DIVE:**
{combined_specialist_analysis}
---
**ASPECT & PATTERN SYNTHESIS:**
{weaver_analysis}
---

**Your Task:**
Write a comprehensive analysis. Structure your response exactly as follows, using plain text headings without markdown.

**Chart Overview and Core Themes**
(Under this heading, write an in-depth interpretive introduction (minimum 4 paragraphs). Focus on clarity, depth, and insight—not just listing placements. Your task:
1. Identify 3–4 core psychological or life themes based on the Foundational Themes, Nodes, Numerology, and Ascendant contrast.
2. For each theme, explain it fully: how it arises, what internal tension or motivation it represents, and what its life lesson is.
3. Draw explicitly from both the Sidereal and Tropical layers, showing how the soul path and personality expression either support or challenge each other.
4. Integrate Numerology and Chinese Zodiac only if they reinforce the astrology—not as separate trivia.
5. Avoid listing too many placements without explanation. Instead, choose a few powerful combinations and explain them in rich psychological detail.
6. Use metaphors, examples, or hypothetical behaviors where appropriate to make each theme emotionally resonant and memorable.
7. Ensure this overview is at least 700–900 words long. Prioritize depth over breadth.)

**Your Personality Blueprint: The Planets**
(Under this heading, present the detailed analysis for each planet. **For each planet from the Sun to Pluto, you must present the FOUR paragraphs (Sidereal Interpretation, Tropical Interpretation, Synthesis, Aspect Analysis) exactly as they were generated in the 'PLANETARY DEEP DIVE' section.** Do not summarize or combine them. Ensure there is a clear separation between each planet's section using a "--- PLANET NAME ---" header and line breaks. Group them thematically: start with the Luminaries (Sun and Moon), then the Personal Planets (Mercury, Venus, Mars), and conclude with the Generational Planets. Create smooth, one-sentence transitions between each planet's analysis.)

**Major Life Dynamics: Aspects and Patterns**
(Under this heading, insert the complete, unedited text from the 'ASPECT & PATTERN SYNTHESIS' analysis. Do not summarize or re-interpret it.)

**Summary and Key Takeaways**
(Under this heading, write a practical, empowering conclusion that summarizes the most important takeaways from the chart. Offer guidance on key areas for personal growth and self-awareness. This section should be at least 500 words.)
"""
        return await _run_gemini_prompt(storyteller_prompt)

    except Exception as e:
        logger.error(f"Error during multi-step Gemini reading: {e}", exc_info=True)
        return "An error occurred while generating the detailed AI reading."


# --- API Endpoints ---

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

        try:
            local_time = pendulum.datetime(
                data.year, data.month, data.day, data.hour, data.minute, tz=timezone_name
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date provided: {data.month}/{data.day}/{data.year}")

        utc_time = local_time.in_timezone('UTC')

        chart = NatalChart(
            name=data.full_name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng,
            local_hour=data.hour
        )
        chart.calculate_chart(unknown_time=data.unknown_time)
        
        numerology = calculate_numerology(data.day, data.month, data.year)
        
        name_numerology = None
        name_parts = data.full_name.strip().split()
        if not data.no_full_name and len(name_parts) >= 3:
            name_numerology = calculate_name_numerology(data.full_name)
            
        chinese_zodiac = get_chinese_zodiac_and_element(data.year, data.month, data.day)
        
        full_response = chart.get_full_chart_data(numerology, name_numerology, chinese_zodiac, data.unknown_time)
            
        return full_response

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred: {type(e).__name__} - {e}", exc_info=True)
        print("\n--- AN EXCEPTION WAS CAUGHT ---"); traceback.print_exc(); print("-----------------------------\n")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {type(e).__name__} - {e}")

@app.post("/generate_reading")
@limiter.limit("3/month")
async def generate_reading_endpoint(request: Request, reading_data: ReadingRequest):
    """
    This endpoint now runs the AI generation synchronously and returns the result to the user.
    Email functionality has been removed.
    """
    try:
        gemini_reading = await get_gemini_reading(reading_data.chart_data, reading_data.unknown_time)
        
        # Log that a chart was generated for the admin, but don't send an email.
        user_inputs = reading_data.user_inputs
        chart_name = user_inputs.get('full_name', 'N/A')
        logger.info(f"AI Reading generated for: {chart_name}")

        return {"gemini_reading": gemini_reading}
    
    except Exception as e:
        logger.error(f"Error in /generate_reading endpoint: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while generating the AI reading.")

