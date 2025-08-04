from fastapi import FastAPI, HTTPException
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
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

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

# --- SETUP SENDGRID ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

app = FastAPI(title="True Sidereal API", version="1.0")

@app.get("/ping")
def ping():
    return {"message": "ok"}

origins = [
    "https://true-sidereal-birth-chart.onrender.com",
    "https://synthesisastrology.org",
    "https://www.synthesisastrology.org",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["POST", "GET", "HEAD", "OPTIONS"],
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
    user_email: Optional[str] = None
    no_full_name: bool = False

class ReadingRequest(BaseModel):
    chart_data: Dict[str, Any]
    unknown_time: bool
    user_inputs: Dict[str, Any]
    chart_image_base64: Optional[str] = None

# --- EMAIL FORMATTING & SENDING ---

def get_full_text_report(res: dict) -> str:
    # This function remains the same as before...
    out = f"=== TRUE SIDEREAL CHART: {res.get('name', 'N/A')} ===\n"
    out += f"- UTC Date & Time: {res.get('utc_datetime', 'N/A')}{' (Noon Estimate)' if res.get('unknown_time') else ''}\n"
    out += f"- Location: {res.get('location', 'N/A')}\n"
    out += f"- Day/Night Determination: {res.get('day_night_status', 'N/A')}\n\n"
    
    out += f"--- CHINESE ZODIAC ---\n"
    out += f"- Your sign is the {res.get('chinese_zodiac', 'N/A')}\n\n"

    if res.get('numerology_analysis'):
        numerology = res['numerology_analysis']
        out += f"--- NUMEROLOGY REPORT ---\n"
        out += f"- Life Path Number: {numerology.get('life_path_number', 'N/A')}\n"
        out += f"- Day Number: {numerology.get('day_number', 'N/A')}\n"
        if numerology.get('name_numerology'):
            name_numerology = numerology['name_numerology']
            out += f"\n-- NAME NUMEROLOGY --\n"
            out += f"- Expression (Destiny) Number: {name_numerology.get('expression_number', 'N/A')}\n"
            out += f"- Soul Urge Number: {name_numerology.get('soul_urge_number', 'N/A')}\n"
            out += f"- Personality Number: {name_numerology.get('personality_number', 'N/A')}\n"
    
    if res.get('sidereal_chart_analysis'):
        analysis = res['sidereal_chart_analysis']
        out += f"\n-- SIDEREAL CHART ANALYSIS --\n"
        out += f"- Chart Ruler: {analysis.get('chart_ruler', 'N/A')}\n"
        out += f"- Dominant Sign: {analysis.get('dominant_sign', 'N/A')}\n"
        out += f"- Dominant Element: {analysis.get('dominant_element', 'N/A')}\n"
        out += f"- Dominant Modality: {analysis.get('dominant_modality', 'N/A')}\n"
        out += f"- Dominant Planet: {analysis.get('dominant_planet', 'N/A')}\n\n"
        
    out += f"--- MAJOR POSITIONS ---\n"
    if res.get('sidereal_major_positions'):
        for p in res['sidereal_major_positions']:
            line = f"- {p.get('name', '')}: {p.get('position', '')}"
            if p.get('name') not in ['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node']:
                line += f" ({p.get('percentage', 0)}%)"
            if p.get('retrograde'): line += " (Rx)"
            if p.get('house_info'): line += f" {p.get('house_info')}"
            out += f"{line}\n"

    if res.get('sidereal_retrogrades'):
        out += f"\n--- RETROGRADE PLANETS (Energy turned inward) ---\n"
        for p in res['sidereal_retrogrades']:
            out += f"- {p.get('name', 'N/A')}\n"

    out += f"\n--- MAJOR ASPECTS (ranked by influence score) ---\n"
    if res.get('sidereal_aspects'):
        for a in res['sidereal_aspects']:
            out += f"- {a.get('p1_name','')} {a.get('type','')} {a.get('p2_name','')} (orb {a.get('orb','')}, score {a.get('score','')})\n"
    else:
        out += "- No major aspects detected.\n"
        
    out += f"\n--- ASPECT PATTERNS ---\n"
    if res.get('sidereal_aspect_patterns'):
        for p in res['sidereal_aspect_patterns']:
            line = f"- {p.get('description', '')}"
            if p.get('orb'): line += f" (avg orb {p.get('orb')})"
            if p.get('score'): line += f" (score {p.get('score')})"
            out += f"{line}\n"
    else:
        out += "- No major aspect patterns detected.\n"

    if not res.get('unknown_time'):
        out += f"\n--- ADDITIONAL POINTS & ANGLES ---\n"
        if res.get('sidereal_additional_points'):
            for p in res['sidereal_additional_points']:
                line = f"- {p.get('name', '')}: {p.get('info', '')}"
                if p.get('retrograde'): line += " (Rx)"
                out += f"{line}\n"
        out += f"\n--- HOUSE RULERS ---\n"
        if res.get('house_rulers'):
            for house, info in res['house_rulers'].items():
                out += f"- {house}: {info}\n"
        out += f"\n--- HOUSE SIGN DISTRIBUTIONS ---\n"
        if res.get('house_sign_distributions'):
            for house, segments in res['house_sign_distributions'].items():
                out += f"{house}:\n"
                if segments:
                    for seg in segments:
                        out += f"      - {seg}\n"
    else:
        out += f"\n- (House Rulers, House Distributions, and some additional points require a known birth time and are not displayed.)\n"

    if res.get('tropical_major_positions'):
        out += f"\n\n\n=== TROPICAL CHART ===\n\n"
        trop_analysis = res.get('tropical_chart_analysis', {})
        out += f"-- CHART ANALYSIS --\n"
        out += f"- Dominant Sign: {trop_analysis.get('dominant_sign', 'N/A')}\n"
        out += f"- Dominant Element: {trop_analysis.get('dominant_element', 'N/A')}\n"
        out += f"- Dominant Modality: {trop_analysis.get('dominant_modality', 'N/A')}\n"
        out += f"- Dominant Planet: {trop_analysis.get('dominant_planet', 'N/A')}\n\n"
        out += f"--- MAJOR POSITIONS ---\n"
        for p in res['tropical_major_positions']:
            line = f"- {p.get('name', '')}: {p.get('position', '')}"
            if p.get('name') not in ['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'South Node']:
                line += f" ({p.get('percentage', 0)}%)"
            if p.get('retrograde'): line += " (Rx)"
            if p.get('house_info'): line += f" {p.get('house_info')}"
            out += f"{line}\n"

        if res.get('tropical_retrogrades'):
            out += f"\n--- RETROGRADE PLANETS (Energy turned inward) ---\n"
            for p in res['tropical_retrogrades']:
                out += f"- {p.get('name', 'N/A')}\n"

        out += f"\n--- MAJOR ASPECTS (ranked by influence score) ---\n"
        if res.get('tropical_aspects'):
            for a in res['tropical_aspects']:
                out += f"- {a.get('p1_name','')} {a.get('type','')} {a.get('p2_name','')} (orb {a.get('orb','')}, score {a.get('score','')})\n"
        else:
            out += "- No major aspects detected.\n"
            
        out += f"\n--- ASPECT PATTERNS ---\n"
        if res.get('tropical_aspect_patterns'):
            for p in res['tropical_aspect_patterns']:
                line = f"- {p.get('description', '')}"
                if p.get('orb'): line += f" (avg orb {p.get('orb')})"
                if p.get('score'): line += f" (score {p.get('score')})"
                out += f"{line}\n"
        else:
            out += "- No major aspect patterns detected.\n"
            
        if not res.get('unknown_time'):
            out += f"\n--- ADDITIONAL POINTS & ANGLES ---\n"
            if res.get('tropical_additional_points'):
                for p in res['tropical_additional_points']:
                    line = f"- {p.get('name', '')}: {p.get('info', '')}"
                    if p.get('retrograde'): line += " (Rx)"
                    out += f"{line}\n"
    return out

def format_full_report_for_email(chart_data: dict, gemini_reading: str, user_inputs: dict, chart_image_base64: Optional[str], include_inputs: bool = True) -> str:
    html = "<h1>Synthesis Astrology Report</h1>"
    
    if include_inputs:
        html += "<h2>Chart Inputs</h2>"
        html += f"<p><b>Name:</b> {user_inputs.get('full_name', 'N/A')}</p>"
        html += f"<p><b>Birth Date:</b> {user_inputs.get('birth_date', 'N/A')}</p>"
        html += f"<p><b>Birth Time:</b> {user_inputs.get('birth_time', 'N/A')}</p>"
        html += f"<p><b>Location:</b> {user_inputs.get('location', 'N/A')}</p>"
        html += "<hr>"

    if chart_image_base64:
        html += "<h2>Natal Chart Wheel</h2>"
        html += f'<img src="data:image/svg+xml;base64,{chart_image_base64}" alt="Natal Chart Wheel" width="600">'
        html += "<hr>"

    html += "<h2>AI Astrological Synthesis</h2>"
    html += f"<p>{gemini_reading.replace('/n', '<br><br>')}</p>"
    html += "<hr>"

    full_text_report = get_full_text_report(chart_data)
    html += "<h2>Full Astrological Data</h2>"
    html += f"<pre>{full_text_report}</pre>"
    
    return f"<html><head><style>body {{ font-family: sans-serif; }} pre {{ white-space: pre-wrap; word-wrap: break-word; }} img {{ max-width: 100%; height: auto; }}</style></head><body>{html}</body></html>"

def send_chart_email(html_content: str, recipient_email: str, subject: str):
    if not SENDGRID_API_KEY or not ADMIN_EMAIL:
        logger.warning("SendGrid API Key or Admin Email not configured. Skipping email.")
        return

    message = Mail(
        from_email=ADMIN_EMAIL,
        to_emails=recipient_email,
        subject=subject,
        html_content=html_content)
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {recipient_email}, status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending email to {recipient_email}: {e}", exc_info=True)


# --- NEW MULTI-STEP AI PROMPT LOGIC ---

async def _run_gemini_prompt(prompt_text: str) -> str:
    """A helper function to run a single Gemini prompt and return the text."""
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt_text)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in Gemini API call: {e}", exc_info=True)
        return f"An error occurred during a Gemini API call: {e}"

async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    # --- UNKNOWN TIME PROMPT (SINGLE STEP) ---
    if unknown_time:
        # This logic remains the same as before
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

    # --- KNOWN TIME PROMPT (6-STEP CHAIN) ---
    try:
        # Step 1: The Cartographer
        cartographer_data = []
        s_pos = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
        t_pos = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
        for body in ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Ascendant']:
            if body in s_pos and body in t_pos:
                cartographer_data.append(f"- {body}: Sidereal {s_pos[body]['position'].split(' ')[-1]}, Tropical {t_pos[body]['position'].split(' ')[-1]}")
        
        cartographer_prompt = f"""
You are The Cartographer, an astrological data analyst. Your task is to compare the provided Sidereal and Tropical placements and identify the primary points of alignment, tension, and contrast. Do not interpret the meaning of the placements. Your output must be a simple, structured list.

**Data to Analyze:**
{'/n'.join(cartographer_data)}

**Your Task:**
1. For each body, state the relationship between its Sidereal and Tropical sign placements.
2. Label each finding with one of the following classifications: "High Alignment" (same sign), "Moderate Tension" (adjacent signs), or "High Contrast" (signs in different elements/modalities).
3. Output nothing but this list.
"""
        cartographer_analysis = await _run_gemini_prompt(cartographer_prompt)

        # Step 2: The Architect
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
            f"- Life Path Number: {numerology.get('life_path_number')}"
        ]
        architect_prompt = f"""
You are The Architect, a master astrologer who identifies the foundational blueprint of a soul. Your task is to analyze the provided chart data and the alignment map to determine the 3-5 central themes of this person's life.

**Zodiac Definitions:**
- The **Sidereal** placements represent the soul's deeper karmic blueprint, innate spiritual gifts, and ultimate life purpose.
- The **Tropical** placements represent the personality's expression, psychological patterns, and how the soul's purpose manifests in this lifetime.

**Alignment Analysis (from The Cartographer):**
{cartographer_analysis}

**Core Chart Data:**
{'/n'.join(architect_data)}

**Your Task:**
1. Review all provided data.
2. Identify the 3-5 most powerful and interconnected themes that define the core of this chart.
3. For each theme, list the specific Sidereal and Tropical data points that serve as evidence.
4. Output this as a structured list. Do not write a narrative.
"""
        architect_analysis = await _run_gemini_prompt(architect_prompt)

        # Step 3: The Navigator
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
You are The Navigator, an expert in karmic astrology. Your task is to interpret the soul's journey from its past to its future potential, based on the Nodal Axis. Use the provided foundational themes to guide your interpretation.

**Foundational Themes (from The Architect):**
{architect_analysis}

**Nodal Axis Data:**
{'/n'.join(navigator_data)}

**Your Task:**
1.  **Interpret the South Node:** Describe the past-life comfort zones, karmic patterns, and innate gifts represented by the South Node's position in both zodiacs.
2.  **Interpret the North Node:** Describe the soul's mission, growth potential, and the qualities it must develop in this lifetime, as shown by the North Node's position in both zodiacs.
3.  **Synthesize:** In a concluding paragraph, explain how the Sidereal (soul path) and Tropical (personality expression) Nodal placements work together. In your synthesis, highlight how the nodal axis is supported or challenged by the chart's dominant element.
"""
        navigator_analysis = await _run_gemini_prompt(navigator_prompt)

        # Step 4: The Specialist (Concurrent Calls)
        async def run_specialist_for_planet(planet_name):
            s_planet = s_pos.get(planet_name, {})
            t_planet = t_pos.get(planet_name, {})
            
            all_s_aspects = chart_data.get('sidereal_aspects', [])
            planet_s_aspects = sorted([a for a in all_s_aspects if planet_name in a['p1_name'] or planet_name in a['p2_name']], key=lambda x: float(x['orb'][:-1]))[:2]
            s_aspects_text = [f"{a['p1_name']} {a['type']} {a['p2_name']}" for a in planet_s_aspects]

            all_t_aspects = chart_data.get('tropical_aspects', [])
            planet_t_aspects = sorted([a for a in all_t_aspects if planet_name in a['p1_name'] or planet_name in a['p2_name']], key=lambda x: float(x['orb'][:-1]))[:2]
            t_aspects_text = [f"{a['p1_name']} {a['type']} {a['p2_name']}" for a in planet_t_aspects]

            specialist_data = [
                f"- Sidereal Placement: {s_planet.get('position')} in House {s_planet.get('house_num')}, Degree {int(s_planet.get('degrees', 0))}",
                f"- Tropical Placement: {t_planet.get('position')} in House {t_planet.get('house_num')}, Degree {int(t_planet.get('degrees', 0))}",
                f"- Sidereal Aspects: {', '.join(s_aspects_text)}",
                f"- Tropical Aspects: {', '.join(t_aspects_text)}"
            ]
            
            specialist_prompt = f"""
You are The Specialist, an astrologer with deep knowledge of planetary archetypes. Your task is to provide a detailed analysis of {planet_name} based on the provided data and the chart's foundational themes.

**Foundational Themes (from The Architect):**
{architect_analysis}

**Sidereal Sign Boundaries (Degrees):**
{TRUE_SIDEREAL_SIGNS}

**{planet_name} Data:**
{'/n'.join(specialist_data)}

**Your Task:**
1.  **Analyze the Sidereal Placement:** Based on the core themes, interpret the meaning of the Sidereal {planet_name} in its sign and house. How does this relate to the soul's purpose? Consider if the planet is retrograde.
2.  **Analyze the Tropical Placement:** Now, interpret the meaning of the Tropical {planet_name} in its sign and house. How does this express the soul's purpose in the personality?
3.  **Analyze the Degree:** The Sidereal {planet_name} is at {int(s_planet.get('degrees', 0))} degrees. Using the provided Sidereal Sign Boundaries, briefly describe the symbolic meaning of this degree and how it adds nuance to the interpretation.
4.  **Analyze the Aspects:** Explain how the two tightest aspects influence the planet's expression.
5.  **Synthesize:** In a concluding paragraph, create a unified interpretation of this planet's role in the person's life, showing how the soul's purpose (Sidereal) is expressed through the personality (Tropical). Explain how the Tropical placement either helps or creates challenges for the Sidereal placement.
"""
            return f"--- ANALYSIS FOR {planet_name.upper()} ---\n{await _run_gemini_prompt(specialist_prompt)}"

        planets_to_analyze = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        specialist_tasks = [run_specialist_for_planet(p) for p in planets_to_analyze]
        specialist_analyses = await asyncio.gather(*specialist_tasks)
        combined_specialist_analysis = "\n\n".join(specialist_analyses)

        # Step 5: The Weaver
        weaver_data = [p.get('description', '') for p in chart_data.get('sidereal_aspect_patterns', [])]
        s_tightest_aspects = [f"{a['p1_name']} {a['type']} {a['p2_name']}" for a in chart_data.get('sidereal_aspects', [])[:3]]
        
        weaver_prompt = f"""
You are The Weaver, an astrologer who sees the hidden connections in a chart. Your task is to synthesize the individual planetary analyses by interpreting the major aspect patterns.

**Planetary Analyses (from The Specialist):**
{combined_specialist_analysis}

**Chart Pattern Data:**
- Patterns: {', '.join(weaver_data)}
- Tightest Aspects: {', '.join(s_tightest_aspects)}

**Your Task:**
1.  **Analyze Major Aspects:** Review the planetary analyses. How do the three tightest aspects in the chart create a central dynamic of tension or harmony? Explain how these aspects are core to the user's life story, referencing the planets involved.
2.  **Analyze Chart Patterns:** For each listed chart pattern (T-Square, Stellium, etc.), explain its dynamic. How does it integrate the energies of the involved planets? Refer back to the provided planetary analyses to enrich your interpretation.
"""
        weaver_analysis = await _run_gemini_prompt(weaver_prompt)

        # Step 6: The Storyteller
        storyteller_prompt = f"""
You are The Synthesizer, an insightful astrological consultant who excels at weaving complex data into a clear and compelling narrative. Your skill is in explaining complex astrological data in a practical and grounded way. You will write a comprehensive, in-depth reading based *exclusively* on the structured analysis provided below. Your tone should be insightful and helpful, like a skilled analyst, avoiding overly spiritual or "dreamy" language.

**CRITICAL RULE:** Base your reading *only* on the analysis provided. Do not invent any placements, planets, signs, or aspects that are not explicitly listed in the analysis.

**Provided Analysis:**
---
**ALIGNMENT MAP (from The Cartographer):**
{cartographer_analysis}
---
**FOUNDATIONAL THEMES (from The Architect):**
{architect_analysis}
---
**KARMIC PATH (from The Navigator):**
{navigator_analysis}
---
**PLANETARY DEEP DIVE (from The Specialist):**
{combined_specialist_analysis}
---
**ASPECT & PATTERN SYNTHESIS (from The Weaver):**
{weaver_analysis}
---

**Your Task:**
Write a comprehensive analysis. Structure your response exactly as follows, using plain text headings without markdown.

**Chart Overview and Core Themes**
(Under this heading, write an introduction. Use the Foundational Themes and the Karmic Path analysis to explain the central story and key drivers of this chart in a practical way.)

**Your Personality Blueprint: The Planets**
(Under this heading, provide a detailed, flowing narrative. **Do not simply list each planet's analysis.** Instead, create transitions between them and group them thematically. For example: start with the Luminaries (Sun and Moon) to explain the core identity. Then, discuss the Personal Planets (Mercury, Venus, Mars) to describe the personality's tools. Finally, cover the Generational Planets (Jupiter, Saturn, etc.) to discuss broader life themes. **MANDATORY FORMATTING:** For every astrological placement you discuss, you must first introduce the term and its role, then provide the interpretation. Follow this exact structure: 'Your **Sun**—which represents your core identity and ego—is in the sign of Leo... This is placed in your **9th House**, the area of your chart related to higher learning and philosophy...')

**Major Life Dynamics: Aspects and Patterns**
(Under this heading, explain the major tensions and harmonies in the chart using the Aspect & Pattern Synthesis. Explain how these dynamics play out in the user's life.)

**Summary and Key Takeaways**
(Under this heading, write a practical, empowering conclusion that summarizes the most important takeaways from the chart. Offer guidance on key areas for personal growth and self-awareness.)
"""
        return await _run_gemini_prompt(storyteller_prompt)

    except Exception as e:
        logger.error(f"Error during multi-step Gemini reading: {e}", exc_info=True)
        return "An error occurred while generating the detailed AI reading."


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
async def generate_reading_endpoint(request: ReadingRequest):
    try:
        gemini_reading = await get_gemini_reading(request.chart_data, request.unknown_time)
        
        user_inputs = request.user_inputs
        user_email = user_inputs.get('user_email')
        chart_name = user_inputs.get('full_name', 'N/A')
        chart_image = request.chart_image_base64

        if user_email:
            user_html_content = format_full_report_for_email(request.chart_data, gemini_reading, user_inputs, chart_image, include_inputs=False)
            send_chart_email(user_html_content, user_email, f"Your Astrology Chart Report for {chart_name}")
            
        if ADMIN_EMAIL:
            admin_html_content = format_full_report_for_email(request.chart_data, gemini_reading, user_inputs, chart_image, include_inputs=True)
            send_chart_email(admin_html_content, ADMIN_EMAIL, f"New Chart Generated: {chart_name}")

        return {"gemini_reading": gemini_reading}
    except Exception as e:
        logger.error(f"Error in /generate_reading endpoint: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while generating the AI reading.")
