# api.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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
    "https://synthesisastrology.org/",
    "https://www.synthesisastrology.org/",
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
    chart_data: dict
    unknown_time: bool

def format_report_for_email(chart_data: dict) -> str:
    """Formats a simplified text report into an HTML string for email."""
    text_content = f"Natal Chart Report for: {chart_data.get('name', 'N/A')}\n"
    text_content += f"UTC Time: {chart_data.get('utc_datetime', 'N/A')}\n"
    text_content += f"Location: {chart_data.get('location', 'N/A')}\n\n"
    
    text_content += "--- Major Sidereal Positions ---\n"
    if chart_data.get('sidereal_major_positions'):
        for pos in chart_data['sidereal_major_positions']:
            text_content += f"- {pos.get('name', 'N/A')}: {pos.get('position', 'N/A')}\n"
        
    html_content = f"<html><body><h2>Natal Chart Report</h2><pre>{text_content}</pre><p>For your full report, including your AI reading and visual chart wheel, please visit the website.</p></body></html>"
    return html_content

def send_chart_email(chart_data: dict, recipient_email: str, is_admin_copy: bool = False):
    if not SENDGRID_API_KEY or not ADMIN_EMAIL:
        logger.warning("SendGrid API Key or Admin Email not configured. Skipping email.")
        return

    subject = f"Your Astrology Chart Report for {chart_data.get('name', '')}"
    if is_admin_copy:
        subject = f"New Chart Generated: {chart_data.get('name', '')}"

    html_content = format_report_for_email(chart_data)

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
        s_analysis = chart_data.get("sidereal_chart_analysis", {})
        numerology_analysis = chart_data.get("numerology_analysis", {})
        s_positions = chart_data.get("sidereal_major_positions", [])
        s_aspects = chart_data.get("sidereal_aspects", [])
        sun = next((p for p in s_positions if p['name'] == 'Sun'), None)
        moon = next((p for p in s_positions if p['name'] == 'Moon'), None)
        asc = next((p for p in s_positions if p['name'] == 'Ascendant'), None)

        prompt_parts = []
        prompt_parts.append(
            "You are a helpful astrological assistant. Your goal is to provide a clear, practical, and grounded interpretation of the provided birth chart data. Avoid mystical or overly flowery language. Focus on the psychological and practical implications of the placements."
        )

        prompt_parts.append("\n**Chart Data:**")
        if sun: prompt_parts.append(f"- Sun: {sun['position']}")
        if moon: prompt_parts.append(f"- Moon: {moon['position']}")
        if not unknown_time and asc:
            prompt_parts.append(f"- Ascendant: {asc['position']}")
        if numerology_analysis.get("life_path_number"):
            prompt_parts.append(f"- Life Path Number: {numerology_analysis.get('life_path_number')}")
        
        if s_aspects and len(s_aspects) > 0:
            tightest_aspect = s_aspects[0]
            prompt_parts.append(f"- Most Significant Aspect: {tightest_aspect['p1_name']} {tightest_aspect['type']} {tightest_aspect['p2_name']}")

        prompt_parts.append("\n**Your Task:**")
        prompt_parts.append("""
Structure your response exactly as follows, using plain text headings.

Key Insights
(Under this heading, provide 3-4 bullet points summarizing the most important themes based on the Sun, Moon, Ascendant, and Life Path Number.)

Summary
(Under this heading, write a concise, multi-sentence paragraph that synthesizes these key insights into a practical overview of the person's core personality dynamics. If the birth time is unknown, you must explicitly state that the reading is limited and does not include the Ascendant or house placements.)
""")

        prompt = "\n".join(prompt_parts)

        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = await model.generate_content_async(prompt)
        
        return response.text.strip()
        
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
            raise HTTPException(status_code=400, detail=f"Invalid date provided: {data.month}/{data.day}/{data.year}")

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
        
        if data.full_name != "Current Transits":
            if ADMIN_EMAIL:
                send_chart_email(full_response, ADMIN_EMAIL, is_admin_copy=True)
            if data.user_email:
                send_chart_email(full_response, data.user_email)
            
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
        return {"gemini_reading": gemini_reading}
    except Exception as e:
        logger.error(f"Error in /generate_reading endpoint: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while generating the AI reading.")
