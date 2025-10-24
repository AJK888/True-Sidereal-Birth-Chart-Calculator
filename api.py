from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
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
import smtplib # Using smtplib for Gmail
from email.message import EmailMessage # Using standard email library
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

# --- SETUP GMAIL --- Using Gmail now
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") # Still needed for sending admin copies

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
    user_email: Optional[str] = None
    no_full_name: bool = False

class ReadingRequest(BaseModel):
    chart_data: Dict[str, Any]
    unknown_time: bool
    user_inputs: Dict[str, Any]
    chart_image_base64: Optional[str] = None

# --- Functions ---

def get_full_text_report(res: dict) -> str:
    # This function remains the same.
    out = f"=== SIDEREAL CHART: {res.get('name', 'N/A')} ===\n"
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

# Updated to use Gmail SMTP
def send_chart_email(html_content: str, recipient_email: str, subject: str):
    if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
        logger.warning("Gmail email or app password not configured. Skipping email.")
        return

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = GMAIL_EMAIL
    msg['To'] = recipient_email
    msg.set_content("Please enable HTML to view this report.") # Fallback
    msg.add_alternative(html_content, subtype='html')

    try:
        # Use smtp.gmail.com and port 465 for Gmail SSL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
            logger.info(f"Email sent via Gmail to {recipient_email}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"Gmail Authentication Error: {e.smtp_code} - {e.smtp_error}. Check GMAIL_EMAIL and GMAIL_APP_PASSWORD.", exc_info=True)
    except Exception as e:
        logger.error(f"Error sending email via Gmail to {recipient_email}: {e}", exc_info=True)


async def _run_gemini_prompt(prompt_text: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = await model.generate_content_async(prompt_text)
        # Add basic error checking for empty or blocked responses
        if not response.parts:
             # Check for safety feedback which might indicate blocking
            safety_feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "No feedback available."
            logger.error(f"Gemini response blocked or empty. Safety Feedback: {safety_feedback}. Prompt: {prompt_text[:500]}...") # Log beginning of prompt
            # Raise exception instead of returning error string
            raise Exception(f"Gemini response was blocked or empty. Feedback: {safety_feedback}")
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error in Gemini API call: {e}", exc_info=True)
        # Propagate specific error messages if available
        error_message = f"An error occurred during a Gemini API call: {e}"
        if "response was blocked" in str(e):
             reason = "Safety settings"
             try:
                 block_reason = getattr(e, 'block_reason', 'Unknown')
                 if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
                      block_reason = e.response.prompt_feedback.block_reason
                 reason = str(block_reason)
             except Exception:
                 pass
             error_message = f"Error: The AI's response was blocked due to {reason}. Please try rephrasing or contact support."
        # Raise exception instead of returning error string
        raise Exception(error_message)


async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    if not GEMINI_API_KEY:
        # Raise exception instead of returning error string
        raise Exception("Gemini API key not configured. AI reading is unavailable.")

    # --- Unknown Time Handling ---
    if unknown_time:
        # ... (rest of the unknown time logic remains the same) ...
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
        # Error handling now happens implicitly via raise in _run_gemini_prompt
        return await _run_gemini_prompt("\n".join(prompt_parts))


    # --- Known Time - Multi-Step Process ---
    # Wrap the entire multi-step process in a try...except to catch errors from any step
    try:
        # --- Step 1: Analyze Alignments ---
        cartographer_data = []
        s_pos_all = {p['name']: p for p in chart_data.get('sidereal_major_positions', []) + chart_data.get('sidereal_additional_points', [])}
        t_pos_all = {p['name']: p for p in chart_data.get('tropical_major_positions', []) + chart_data.get('tropical_additional_points', [])}
        
        bodies_for_alignment = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto', 'Chiron', 'True Node', 'Lilith', 'Ascendant', 'Midheaven (MC)', 'Ceres', 'Pallas', 'Juno', 'Vesta']
        for body in bodies_for_alignment:
            s_body_data = s_pos_all.get(body)
            t_body_data = t_pos_all.get(body)
            if s_body_data and t_body_data and s_body_data.get('position') and t_body_data.get('position'):
                 s_sign = s_body_data['position'].split(' ')[-1]
                 t_sign = t_body_data['position'].split(' ')[-1]
                 if s_sign != 'N/A' and t_sign != 'N/A':
                      cartographer_data.append(f"- {body}: Sidereal {s_sign}, Tropical {t_sign}")

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
        # Error check removed, will be caught by outer try/except

        # --- Step 2: Identify Foundational Blueprint ---
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        t_analysis = chart_data.get("tropical_chart_analysis", {})
        numerology = chart_data.get("numerology_analysis", {})
        architect_data = [
            f"- Sidereal Sun: {s_pos_all.get('Sun', {}).get('position')} in House {s_pos_all.get('Sun', {}).get('house_num')}",
            f"- Tropical Sun: {t_pos_all.get('Sun', {}).get('position')} in House {t_pos_all.get('Sun', {}).get('house_num')}",
            f"- Sidereal Moon: {s_pos_all.get('Moon', {}).get('position')} in House {s_pos_all.get('Moon', {}).get('house_num')}",
            f"- Tropical Moon: {t_pos_all.get('Moon', {}).get('position')} in House {t_pos_all.get('Moon', {}).get('house_num')}",
            f"- Sidereal Ascendant: {s_pos_all.get('Ascendant', {}).get('position')}",
            f"- Tropical Ascendant: {t_pos_all.get('Ascendant', {}).get('position')}",
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
        # Error check removed

        # --- Step 3: Interpret Karmic Path ---
        s_north_node = s_pos_all.get('True Node', {})
        s_south_node = s_pos_all.get('South Node', {})
        t_north_node = t_pos_all.get('True Node', {})
        t_south_node = t_pos_all.get('South Node', {})

        navigator_data = [
            f"- Sidereal South Node: {s_south_node.get('position')} in House {s_south_node.get('house_num')}",
            f"- Sidereal North Node: {s_north_node.get('position')} in House {s_north_node.get('house_num')}",
            f"- Tropical South Node: {t_south_node.get('position')} in House {t_south_node.get('house_num')}",
            f"- Tropical North Node: {t_north_node.get('position')} in House {t_north_node.get('house_num')}",
            f"- Dominant Element: {s_analysis.get('dominant_element')}"
        ]
        navigator_prompt = f"""
Interpret the soul's journey from its past to its future potential, based on the Nodal Axis (True Node and implied South Node). Use the provided foundational themes to guide your interpretation.

**Foundational Themes:**
{architect_analysis}

**Nodal Axis Data:**
{'/n'.join(navigator_data)}

**Your Task:**
1.  **Interpret the South Node:** Describe the past-life comfort zones, karmic patterns, and innate gifts represented by the South Node's position in both zodiacs and its house placement.
2.  **Interpret the North Node:** Describe the soul's mission, growth potential, and the qualities it must develop in this lifetime, as shown by the North Node's position in both zodiacs and its house placement.
3.  **Synthesize:** In a concluding paragraph, explain how the Sidereal (soul path) and Tropical (personality expression) Nodal placements work together. In your synthesis, highlight how the nodal axis is supported or challenged by the chart's dominant element.
"""
        navigator_analysis = await _run_gemini_prompt(navigator_prompt)
        # Error check removed

        # --- Step 4: Perform Deep-Dive Point Analysis ---
        async def run_specialist_for_point(point_name):
            s_point = s_pos_all.get(point_name, {})
            t_point = t_pos_all.get(point_name, {})

            has_retrograde = point_name not in ['Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)', 'True Node', 'South Node', 'Part of Fortune', 'Vertex']
            retrograde_status = 'Yes' if has_retrograde and s_point.get('retrograde') else ('No' if has_retrograde else 'N/A')

            specialist_data = [
                 f"- Sidereal Placement: {s_point.get('position', 'N/A')} in House {s_point.get('house_num', 'N/A')}",
                 f"- Tropical Placement: {t_point.get('position', 'N/A')} in House {t_point.get('house_num', 'N/A')}",
            ]
            if has_retrograde:
                 specialist_data.append(f"- Retrograde Status: {retrograde_status}")

            interpretation_focus = f"soul’s core essence and karmic purpose related to {point_name}"
            # ... (dynamic focus adjustments remain the same) ...
            if point_name in ['Ascendant', 'Descendant']:
                 interpretation_focus = f"interface with the world and relationships through {point_name}"
            elif point_name in ['Midheaven (MC)', 'Imum Coeli (IC)']:
                 interpretation_focus = f"public persona/career and private/inner foundation through {point_name}"
            elif point_name == 'True Node':
                 interpretation_focus = "soul's evolutionary direction and path of growth"
            elif point_name == 'South Node':
                 interpretation_focus = "past life patterns, comfort zones, and innate gifts"
            elif point_name == 'Lilith':
                 interpretation_focus = "shadow self, raw instincts, and areas of potential repression or taboo related to Lilith"
            elif point_name == 'Part of Fortune':
                 interpretation_focus = "point of innate luck, joy, and harmonious expression"
            elif point_name == 'Vertex':
                 interpretation_focus = "point of fated encounters and significant turning points"
            elif point_name == 'Ceres':
                interpretation_focus = "themes of nurturing, self-care, and the mother-child dynamic"
            elif point_name == 'Pallas':
                interpretation_focus = "themes of wisdom, strategy, creative intelligence, and father-daughter dynamics"
            elif point_name == 'Juno':
                interpretation_focus = "themes of committed partnership, marriage, and balance in relationships"
            elif point_name == 'Vesta':
                interpretation_focus = "themes of devotion, sacred focus, purity, and where one's 'inner flame' is dedicated"
            elif point_name == 'Chiron':
                interpretation_focus = "the 'wounded healer' archetype, showing the soul's deepest wound and its greatest gift of healing"


            specialist_prompt = f"""
You are an expert astrologer trained in both Sidereal and Tropical systems. For the point/body '{point_name}', you must write three separate, detailed paragraphs: one for its Sidereal interpretation, one for its Tropical interpretation, and a third for synthesizing these views. Use precise astrological terminology and explain your reasoning.

**Foundational Themes (Context Only):**
{architect_analysis}

**{point_name} Data:**
{'/n'.join(specialist_data)}

**Your Task:**
Write three clearly separated, detailed paragraphs:

**Sidereal Interpretation:**
(In this paragraph, explain the {interpretation_focus} within the Sidereal zodiac. Analyze its placement in its **sign AND house**. Explain the psychological implications of the house placement. Discuss relevant factors like element and modality. If Retrograde Status is 'Yes', explain the impact of its internalized energy.)

**Tropical Interpretation:**
(In this paragraph, explain how the Sidereal energy manifests through the personality via {point_name} in the Tropical zodiac. Analyze its placement in its **sign AND house**. Explain how the house placement affects its behavioral expression and interaction with the Sidereal placement.)

**Synthesis:**
(In this paragraph, compare the Sidereal vs. Tropical expressions for {point_name}. Are they aligned, in tension, or complementary? How does the house placement in one system support or challenge the other?)
"""
            # Error handling inside _run_gemini_prompt will raise exception on failure
            result_text = await _run_gemini_prompt(specialist_prompt)
            return f"--- {point_name.upper()} ---\n{result_text}"

        points_to_analyze = [
            'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
            'Ascendant', 'Descendant', 'Midheaven (MC)', 'Imum Coeli (IC)',
            'True Node', 'South Node',
            'Chiron', 'Lilith', 'Ceres', 'Pallas', 'Juno', 'Vesta',
            'Part of Fortune', 'Vertex'
        ]

        # Use asyncio.gather with return_exceptions=True to handle potential errors in parallel calls
        specialist_tasks_results = await asyncio.gather(
            *[run_specialist_for_point(p) for p in points_to_analyze if p in s_pos_all],
            return_exceptions=True
        )
        
        # Check results for exceptions
        combined_specialist_analysis_parts = []
        for result in specialist_tasks_results:
            if isinstance(result, Exception):
                logger.error(f"Error during specialist analysis step: {result}", exc_info=result)
                # Option 1: Raise the first exception encountered
                raise result 
            else:
                combined_specialist_analysis_parts.append(result)
        combined_specialist_analysis = "\n\n".join(combined_specialist_analysis_parts)


        # --- Step 5: Analyze Tightest Aspects (Updated to 8) ---
        s_tightest_aspects = chart_data.get('sidereal_aspects', [])[:8] # Changed from 5 to 8
        aspect_data_for_prompt = []
        for a in s_tightest_aspects:
             p1_name_base = a['p1_name'].split(' in ')[0]
             p2_name_base = a['p2_name'].split(' in ')[0]
             p1_house = s_pos_all.get(p1_name_base, {}).get('house_num', 'N/A')
             p2_house = s_pos_all.get(p2_name_base, {}).get('house_num', 'N/A')
             p1_rx = " (Rx)" if s_pos_all.get(p1_name_base, {}).get('retrograde') else ""
             p2_rx = " (Rx)" if s_pos_all.get(p2_name_base, {}).get('retrograde') else ""
             aspect_data_for_prompt.append(f"- {a['p1_name']}{p1_rx} (House {p1_house}) {a['type']} {a['p2_name']}{p2_rx} (House {p2_house}) (orb {a['orb']}, score {a['score']})")


        weaver_prompt = f"""
You are The Weaver, an astrologer who sees the hidden connections in a chart. Your task is to synthesize the individual planetary analyses by interpreting ONLY the **eight** tightest aspects in the Sidereal chart overall.

**Planetary & Point Analyses (Context Only):** (Briefly review the core meaning of bodies involved in the tightest aspects below if needed from this text block, but DO NOT reference this block directly in your output.)
{combined_specialist_analysis} 

**Top 8 Tightest Sidereal Aspects:**
{'/n'.join(aspect_data_for_prompt)}

**Your Task:**
**Analyze Tightest Aspects:** For each of the **eight** tightest aspects listed above, write a dedicated, detailed paragraph (**8 paragraphs total**). Explain the dynamic it creates between the two bodies involved, referencing their signs and houses as provided in the aspect string. Describe how this specific aspect energy is likely to manifest as a core life theme or psychological dynamic, representing a central challenge, strength, or unique characteristic for the individual. Focus on providing insightful interpretation for each aspect individually. Output ONLY these 8 paragraphs, clearly separated.
"""
        weaver_analysis = await _run_gemini_prompt(weaver_prompt)
        # Error check removed

        # --- Step 6: Final Synthesis (Updated to 8 aspects) ---
        storyteller_prompt = f"""
You are The Synthesizer, an insightful astrological consultant who excels at weaving complex data into a clear and compelling narrative. Your skill is in explaining complex astrological data in a practical and grounded way. You will write a comprehensive, in-depth reading based *exclusively* on the structured analysis provided below. Your tone should be insightful and helpful, avoiding overly spiritual or "dreamy" language.

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
**PLANETARY & POINT DEEP DIVE (3 paragraphs per body):** {combined_specialist_analysis}
---
**TIGHTEST ASPECTS ANALYSIS (Top 8 Sidereal):**
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
5. Avoid listing too many placements without explanation. Instead, choose a few powerful combinations (e.g., Sun/Moon/Ascendant, key aspects, nodal placements) and explain them in rich psychological detail.
6. Use metaphors, examples, or hypothetical behaviors where appropriate to make each theme emotionally resonant and memorable.
7. Ensure this overview is at least 700–900 words long. Prioritize depth over breadth.)

**Your Astrological Blueprint: Planets, Points, and Angles**
(Under this heading, present the detailed analysis for each body. **For each body analyzed in the 'PLANETARY & POINT DEEP DIVE' section, you must present the THREE paragraphs (Sidereal Interpretation, Tropical Interpretation, Synthesis) exactly as they were generated.** Do not summarize or combine them. Ensure there is a clear separation between each body's section using a "--- BODY NAME ---" header and line breaks. Group them thematically: Luminaries (Sun, Moon), Personal Planets (Mercury, Venus, Mars), Generational Planets (Jupiter, Saturn, Uranus, Neptune, Pluto), Angles (Ascendant, Descendant, Midheaven, Imum Coeli), Nodes (True Node, South Node), Major Asteroids (Chiron, Ceres, Pallas, Juno, Vesta, Lilith), Other Points (Part of Fortune, Vertex). Create smooth, one-sentence transitions between each body's analysis.)

**Major Life Dynamics: The Tightest Aspects**
(Under this heading, insert the complete, unedited text from the 'TIGHTEST ASPECTS ANALYSIS' section, containing the **8** detailed paragraphs about the top 8 Sidereal aspects.)

**Summary and Key Takeaways**
(Under this heading, write a practical, empowering conclusion that summarizes the most important takeaways from the chart. Offer guidance on key areas for personal growth and self-awareness based *only* on the preceding analysis. This section should be at least 500 words.)
"""
        final_reading = await _run_gemini_prompt(storyteller_prompt)
        # Error check removed
        return final_reading

    except Exception as e:
        # Catch errors from any step in the known-time process
        logger.error(f"Error during multi-step Gemini reading (known time): {e}", exc_info=True)
        # Raise the exception to be handled by the endpoint
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")


# Simplified background task ONLY for sending emails
async def send_emails_in_background(chart_data: Dict, gemini_reading: str, user_inputs: Dict, chart_image_base64: Optional[str]):
    try:
        logger.info("Starting background task for email sending.")
        user_email = user_inputs.get('user_email')
        chart_name = user_inputs.get('full_name', 'N/A')

        # Send email to the user (if provided)
        if user_email:
            user_html_content = format_full_report_for_email(chart_data, gemini_reading, user_inputs, chart_image_base64, include_inputs=False)
            send_chart_email(user_html_content, user_email, f"Your Astrology Chart Report for {chart_name}")
            
        # Send email to the admin (if configured)
        admin_email_to_send_to = os.getenv("ADMIN_EMAIL") # Get admin email inside task
        if admin_email_to_send_to:
            admin_html_content = format_full_report_for_email(chart_data, gemini_reading, user_inputs, chart_image_base64, include_inputs=True)
            send_chart_email(admin_html_content, admin_email_to_send_to, f"New Chart Generated: {chart_name}")
        
        logger.info(f"Email background task completed for {chart_name}.")
    except Exception as e:
        logger.error(f"Error in email background task: {e}", exc_info=True)


@app.post("/calculate_chart")
async def calculate_chart_endpoint(data: ChartRequest):
    try:
        log_data = data.dict()
        if 'full_name' in log_data:
            log_data['chart_name'] = log_data.pop('full_name')
        logger.info("New chart request received", extra=log_data)

        # Ensure ephemeris files are accessible
        ephe_path = os.getenv("SWEP_PATH", ".") # Allow overriding path via env var if needed
        if not os.path.exists(ephe_path):
             logger.warning(f"Ephemeris path '{ephe_path}' not found. Falling back to default.")
             ephe_path = "." # Fallback just in case
        swe.set_ephe_path(ephe_path.encode('utf-8')) # Encode path for swisseph

        opencage_key = os.getenv("OPENCAGE_KEY")
        if not opencage_key:
            raise HTTPException(status_code=500, detail="Server is missing the geocoding API key.")
        
        geo_url = f"https://api.opencagedata.com/geocode/v1/json?q={data.location}&key={opencage_key}"
        response = requests.get(geo_url, timeout=10)
        response.raise_for_status()
        geo_res = response.json()

        results = geo_res.get("results", [])
        if not results:
             raise HTTPException(status_code=400, detail=f"Could not find location data for '{data.location}'. Please be more specific (e.g., City, State, Country).")
        
        result = results[0]
        geometry = result.get("geometry", {})
        annotations = result.get("annotations", {}).get("timezone", {})
        lat, lng, timezone_name = geometry.get("lat"), geometry.get("lng"), annotations.get("name")

        if not all([isinstance(lat, (int, float)), isinstance(lng, (int, float)), timezone_name]):
             logger.error(f"Incomplete location data retrieved: lat={lat}, lng={lng}, tz={timezone_name}")
             # FIX: Corrected the invalid decimal literal '4D_CHART_ANALYSIS' to '400'
             raise HTTPException(status_code=400, detail="Could not retrieve complete location data (latitude, longitude, timezone).")

        try:
            local_time = pendulum.datetime(
                data.year, data.month, data.day, data.hour, data.minute, tz=timezone_name
            )
        except ValueError as e:
            logger.error(f"Invalid date/time/timezone: Y={data.year}, M={data.month}, D={data.day}, H={data.hour}, Min={data.minute}, TZ={timezone_name}. Error: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid date, time, or timezone provided: {data.month}/{data.day}/{data.year} {data.hour}:{data.minute:02d} {timezone_name}")
        except Exception as e: # Catch broader pendulum errors
            logger.error(f"Pendulum error: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Error processing date/time/timezone: {e}")


        utc_time = local_time.in_timezone('UTC')

        chart = NatalChart(
            name=data.full_name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng,
            local_hour=data.hour # Pass local hour for day/night calc
        )
        chart.calculate_chart(unknown_time=data.unknown_time)
        
        numerology = calculate_numerology(data.day, data.month, data.year)
        
        name_numerology = None
        name_parts = data.full_name.strip().split()
        # Ensure name numerology is only calculated if requested and name seems valid
        if not data.no_full_name and len(name_parts) >= 2: # Relaxed check slightly
            try:
                name_numerology = calculate_name_numerology(data.full_name)
            except Exception as e:
                 logger.warning(f"Could not calculate name numerology for '{data.full_name}': {e}")
                 name_numerology = None # Ensure it's None if calculation fails
            
        chinese_zodiac = get_chinese_zodiac_and_element(data.year, data.month, data.day)
        
        full_response = chart.get_full_chart_data(numerology, name_numerology, chinese_zodiac, data.unknown_time)
            
        return full_response

    except HTTPException as e:
        # Log HTTP exceptions before re-raising
        logger.error(f"HTTP Exception in /calculate_chart: {e.status_code} - {e.detail}", exc_info=True)
        raise e
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding API request failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Could not connect to the geocoding service.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in /calculate_chart: {type(e).__name__} - {e}", exc_info=True)
        # traceback.print_exc() # Keep printing for debugging if needed
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {type(e).__name__}")


@app.post("/generate_reading")
@limiter.limit("3/month")
async def generate_reading_endpoint(
    request: Request,
    reading_data: ReadingRequest,
    background_tasks: BackgroundTasks
):
    """
    This endpoint runs the AI generation synchronously to return to the user,
    and handles email sending in the background using Gmail SMTP.
    """
    try:
        # Run AI generation synchronously
        gemini_reading = await get_gemini_reading(reading_data.chart_data, reading_data.unknown_time)
        
        # Log basic info
        user_inputs = reading_data.user_inputs
        chart_name = user_inputs.get('full_name', 'N/A')
        logger.info(f"AI Reading successfully generated for: {chart_name}") # Log success before email attempt

        # Add ONLY the email sending to a background task
        background_tasks.add_task(
            send_emails_in_background,
            chart_data=reading_data.chart_data,
            gemini_reading=gemini_reading,
            user_inputs=user_inputs,
            chart_image_base64=reading_data.chart_image_base64
        )

        # Return the reading to the frontend
        return {"gemini_reading": gemini_reading}
    
    # Handle exceptions specifically from get_gemini_reading
    except Exception as e: 
        logger.error(f"Error during AI reading generation in endpoint: {e}", exc_info=True)
        # Raise HTTPException to send error detail back to frontend
        raise HTTPException(status_code=500, detail=str(e))

