from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
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

def get_full_text_report(res: dict) -> str:
    """Generates the full plain text report from chart data."""
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

def format_full_report_for_email(chart_data: dict, gemini_reading: str, user_inputs: dict) -> str:
    """Formats the complete report into an HTML string for email."""
    # 1. User Inputs
    html = "<h1>Synthesis Astrology Report</h1>"
    html += "<h2>Chart Inputs</h2>"
    html += f"<p><b>Name:</b> {user_inputs.get('full_name', 'N/A')}</p>"
    html += f"<p><b>Birth Date:</b> {user_inputs.get('birth_date', 'N/A')}</p>"
    html += f"<p><b>Birth Time:</b> {user_inputs.get('birth_time', 'N/A')}</p>"
    html += f"<p><b>Location:</b> {user_inputs.get('location', 'N/A')}</p>"
    html += "<hr>"

    # 2. AI Synthesis
    html += "<h2>AI Astrological Synthesis</h2>"
    html += f"<p>{gemini_reading.replace('/n', '<br>')}</p>"
    html += "<hr>"

    # 3. Full Text Report
    full_text_report = get_full_text_report(chart_data)
    html += "<h2>Full Astrological Data</h2>"
    html += f"<pre>{full_text_report}</pre>"
    
    return f"<html><head><style>body {{ font-family: sans-serif; }} pre {{ white-space: pre-wrap; word-wrap: break-word; }}</style></head><body>{html}</body></html>"

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


async def get_gemini_reading(chart_data: dict, unknown_time: bool) -> str:
    if not GEMINI_API_KEY:
        return "Gemini API key not configured. AI reading is unavailable."

    try:
        model = genai.GenerModel('gemini-1.5-pro-latest')
        prompt_parts = []
        
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        s_patterns = chart_data.get("sidereal_aspect_patterns", [])
        s_retrogrades = chart_data.get("sidereal_retrogrades", [])
        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)

        if unknown_time:
            prompt_parts.append(
                "You are a wise astrologer providing a reading for a chart where the exact birth time is unknown. "
                "This is called a 'Noon Chart'.\n"
                "**Your most important rule is to completely avoid mentioning the Ascendant, Midheaven (MC), Chart Ruler, or any House placements, as they are unknown and cannot be used.** "
                "You must focus exclusively on the placement of planets in their signs, the aspects between them, and the numerology."
            )
            prompt_parts.append("\n**Anonymized Chart Data (Noon Calculation - Time-Sensitive Data Excluded):**")
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
            final_response = await model.generate_content_async("\n".join(prompt_parts))
            return final_response.text.strip()

        else:
            analyst_prompt_parts = [
                "You are a master astrological analyst. Your task is to review the provided raw chart data and extract ONLY the most critical, interconnected themes and their corresponding astrological evidence. Be concise, structured, and use bullet points. **Do not invent any placements.** Your output will be used by another AI to write the final reading."
            ]
            analyst_prompt_parts.append("\n**Full Anonymized Chart Data:**")
            asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)
            if sun: analyst_prompt_parts.append(f"- Sun: {sun['position']} ({sun['percentage']}%)")
            if moon: analyst_prompt_parts.append(f"- Moon: {moon['position']} ({moon['percentage']}%)")
            if asc: analyst_prompt_parts.append(f"- Ascendant: {asc['position']} ({asc['percentage']}%)")
            if s_analysis.get("chart_ruler"): analyst_prompt_parts.append(f"- Chart Ruler: {s_analysis['chart_ruler']}")
            if s_analysis.get("dominant_planet"): analyst_prompt_parts.append(f"- Dominant Planet: {s_analysis['dominant_planet']}")
            if s_analysis.get("dominant_sign"): analyst_prompt_parts.append(f"- Dominant Sign: {s_analysis['dominant_sign']}")
            if s_analysis.get("dominant_element"): analyst_prompt_parts.append(f"- Dominant Element: {s_analysis['dominant_element']}")
            if numerology_analysis.get("life_path_number"): analyst_prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
            if numerology_analysis.get("day_number"): analyst_prompt_parts.append(f"- Day Number: {numerology_analysis.get('day_number')}")
            if s_patterns:
                for pattern in s_patterns: analyst_prompt_parts.append(f"- Pattern: {pattern}")
            if s_retrogrades:
                for planet in s_retrogrades: analyst_prompt_parts.append(f"- Retrograde: {planet['name']}")
            if s_aspects and len(s_aspects) >= 3:
                for aspect in s_aspects[:3]: analyst_prompt_parts.append(f"- Tight Aspect: {aspect['p1_name']} {aspect['type']} {aspect['p2_name']}")

            analyst_prompt_parts.append("\n**Your Task:**")
            analyst_prompt_parts.append(
                "1. Identify the 3-5 most powerful and interconnected themes in the chart.\n"
                "2. For each theme, list the specific data points that support it.\n"
                "3. Output this information as a structured list."
            )
            analysis_response = await model.generate_content_async("\n".join(analyst_prompt_parts))
            structured_analysis = analysis_response.text

            teacher_prompt_parts = [
                "You are a master astrologer and gifted teacher. Your skill is not just in seeing the connections in a chart, but in explaining them with depth, patience, and clarity. You identify the 'golden thread'—the central narrative—that connects every placement. **Crucially, you must base your reading exclusively and entirely on the analysis provided. Do not invent any placements, planets (e.g., 'Earth'), or signs that are not explicitly listed in the analysis.**",
                "\nHere is the structured analysis of a user's chart:",
                "--- ANALYSIS START ---",
                structured_analysis,
                "--- ANALYSIS END ---",
                "\n**Your Task:**",
                "Write a generous, in-depth, multi-paragraph reading based on the analysis above. **Prioritize thorough explanation over brevity.** Structure your response **exactly as follows**, using plain text headings.",
                "\nKey Themes in Your Chart",
                "(Under this heading, list the main themes from the analysis.)",
                "\nThe Central Story of Your Chart",
                "(Under this heading, write the full narrative. Do not just repeat the analysis; expand and explain it.)",
                "- For every astrological term (e.g., Sun, Leo, 9th House, Trine, Stellium), you **must** provide a simple, one-sentence definition.",
                "- **MANDATORY INTEGRATION:** Seamlessly integrate **all stelliums**, the **Chart Ruler**, the **Life Path and Day Numbers**, and the **three tightest aspects** into a single, flowing narrative.",
                "- **Make connections explicit.** Your explanation should follow this logic: 'Your core identity, represented by your Sun's placement, is fundamentally about X. This is the very mission statement of your soul, which is perfectly echoed by your Life Path Number Y, the number of Z.'",
                "- Conclude with a warm, empowering summary."
            ]
            final_response = await model.generate_content_async("\n".join(teacher_prompt_parts))
            return final_response.text.strip()
        
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

        try:
            local_time = pendulum.datetime(
                data.year, data.month, data.day, data.hour, data.minute, tz=timezone_name
            )
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date provided: {data.month}/{data.day}/{year}")

        utc_time = local_time.in_timezone('UTC')

        chart = NatalChart(
            name=data.full_name, year=utc_time.year, month=utc_time.month, day=utc_time.day,
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng,
            local_hour=data.hour
        )
        chart.calculate_chart()
        
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

        # Always prepare the full report content, regardless of whether a user email was provided.
        html_content = format_full_report_for_email(request.chart_data, gemini_reading, user_inputs)

        # Send to user if they provided an email
        if user_email:
            send_chart_email(html_content, user_email, f"Your Astrology Chart Report for {chart_name}")
            
        # ALWAYS send to admin, as long as the admin email is configured.
        if ADMIN_EMAIL:
            send_chart_email(html_content, ADMIN_EMAIL, f"New Chart Generated: {chart_name}")

        return {"gemini_reading": gemini_reading}
    except Exception as e:
        logger.error(f"Error in /generate_reading endpoint: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while generating the AI reading.")
