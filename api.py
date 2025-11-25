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
from slowapi import Limiter
import hashlib
import json
from datetime import datetime, timedelta
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
import uuid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
from pdf_generator import generate_pdf_report
from llm_schemas import (
    ChartOverviewOutput, CoreTheme, serialize_chart_for_llm,
    format_serialized_chart_for_prompt, parse_json_response,
    GlobalReadingBlueprint, LifeAxis, CoreThemeBullet, SNAPSHOT_PROMPT
)

# --- SETUP THE LOGGER ---
import sys

# Always log to stdout so Render shows the logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Ensure logs propagate to root logger
logger.propagate = True

# Always add a StreamHandler to stdout for Render visibility
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Optionally also log to Logtail if configured
logtail_token = os.getenv("LOGTAIL_SOURCE_TOKEN")
if logtail_token:
    ingesting_host = "https://s1450016.eu-nbg-2.betterstackdata.com"
    logtail_handler = LogtailHandler(source_token=logtail_token, host=ingesting_host)
    logger.addHandler(logtail_handler)

# --- SETUP GEMINI ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI3_MODEL = os.getenv("GEMINI3_MODEL", "models/gemini-3.0-pro-exp-01")
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini API client configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure Gemini client: {e}")
else:
    logger.warning("GEMINI_API_KEY not configured - Gemini 3 readings unavailable unless AI_MODE=stub")

# --- SETUP SENDGRID ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")  # Verified sender email in SendGrid
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")  # Admin email for receiving copies

# --- Swiss Ephemeris configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SWISS_EPHEMERIS_PATH = os.path.join(BASE_DIR, "swiss_ephemeris")

# --- Admin Secret Key for bypassing rate limit ---
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

# --- Reading Cache for Frontend Polling ---
# In-memory cache to store completed readings (key: chart_hash, value: {reading, timestamp})
reading_cache: Dict[str, Dict[str, Any]] = {}
CACHE_EXPIRY_HOURS = 24  # Readings expire after 24 hours

def generate_chart_hash(chart_data: Dict, unknown_time: bool) -> str:
    """Generate a unique hash from chart data for caching."""
    # Create a stable representation of the chart data
    key_data = {
        'unknown_time': unknown_time,
        'major_positions': chart_data.get('sidereal_major_positions', []),
        'aspects': chart_data.get('sidereal_aspects', [])
    }
    # Sort lists to ensure consistent hashing
    if isinstance(key_data['major_positions'], list):
        key_data['major_positions'] = sorted(key_data['major_positions'], key=lambda x: x.get('name', ''))
    if isinstance(key_data['aspects'], list):
        key_data['aspects'] = sorted(key_data['aspects'], key=lambda x: (x.get('p1_name', ''), x.get('p2_name', '')))
    
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_string.encode()).hexdigest()[:16]  # Use first 16 chars

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

# --- CORS MIDDLEWARE (MUST BE ADDED BEFORE ROUTES) ---
origins = [
    "https://synthesisastrology.org",
    "https://www.synthesisastrology.org",
    "https://synthesisastrology.com",
    "https://www.synthesisastrology.com",
    "https://true-sidereal-birth-chart.onrender.com",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Thank you for using Synthesis Astrology. Due to high API costs we limit user's requests for readings. Please reach out to the developer if you would like them to provide you a reading."}
    )

@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return {"message": "ok"}


@app.get("/")
def root():
    """Simple root endpoint so uptime monitors don't hit a 404."""
    return {"message": "ok"}

@app.get("/check_email_config")
def check_email_config():
    """Diagnostic endpoint to check SendGrid email configuration."""
    config_status = {
        "sendgrid_api_key": {
            "configured": bool(SENDGRID_API_KEY),
            "length": len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 0,
            "preview": f"{SENDGRID_API_KEY[:10]}..." if SENDGRID_API_KEY and len(SENDGRID_API_KEY) > 10 else "Not set"
        },
        "sendgrid_from_email": {
            "configured": bool(SENDGRID_FROM_EMAIL),
            "value": SENDGRID_FROM_EMAIL if SENDGRID_FROM_EMAIL else "Not set"
        },
        "admin_email": {
            "configured": bool(ADMIN_EMAIL),
            "value": ADMIN_EMAIL if ADMIN_EMAIL else "Not set"
        },
        "email_sending_ready": bool(SENDGRID_API_KEY and SENDGRID_FROM_EMAIL)
    }
    
    # Log the configuration check
    logger.info("="*60)
    logger.info("Email Configuration Check")
    logger.info("="*60)
    logger.info(f"SENDGRID_API_KEY configured: {config_status['sendgrid_api_key']['configured']} (length: {config_status['sendgrid_api_key']['length']})")
    logger.info(f"SENDGRID_FROM_EMAIL configured: {config_status['sendgrid_from_email']['configured']} (value: {config_status['sendgrid_from_email']['value']})")
    logger.info(f"ADMIN_EMAIL configured: {config_status['admin_email']['configured']} (value: {config_status['admin_email']['value']})")
    logger.info(f"Email sending ready: {config_status['email_sending_ready']}")
    logger.info("="*60)
    
    return config_status

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
    user_email: Optional[str] = None  # User email for sending chart report
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

def format_full_report_for_email(chart_data: dict, reading_text: str, user_inputs: dict, chart_image_base64: Optional[str], include_inputs: bool = True) -> str:
    # Note: This function is deprecated - PDF generation is used instead
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
    html += f"<p>{reading_text.replace('\\n', '<br><br>')}</p>"
    html += "<hr>"

    full_text_report = get_full_text_report(chart_data)
    html += "<h2>Full Astrological Data</h2>"
    html += f"<pre>{full_text_report}</pre>"
    
    return f"<html><head><style>body {{ font-family: sans-serif; }} pre {{ white-space: pre-wrap; word-wrap: break-word; }} img {{ max-width: 100%; height: auto; }}</style></head><body>{html}</body></html>"

def _safe_get_tokens(usage: dict, key: str) -> int:
    """Safely extract token count from usage metadata, handling None and invalid values."""
    if not usage or not isinstance(usage, dict):
        return 0
    value = usage.get(key, 0)
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def calculate_gemini3_cost(prompt_tokens: int, completion_tokens: int,
                           input_price_per_million: float = 2.00,
                           output_price_per_million: float = 12.00) -> dict:
    """
    Calculate Gemini 3 Pro API cost based on token usage.
    
    Default pricing (per 1M tokens):
    - Input: $2.00
    - Output: $12.00
    """
    try:
        prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else 0
        completion_tokens = int(completion_tokens) if completion_tokens is not None else 0
        prompt_tokens = max(0, prompt_tokens)
        completion_tokens = max(0, completion_tokens)
        
        input_cost = (prompt_tokens / 1_000_000) * input_price_per_million
        output_cost = (completion_tokens / 1_000_000) * output_price_per_million
        total_cost = input_cost + output_cost
        
        return {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens,
            'input_cost_usd': round(input_cost, 6),
            'output_cost_usd': round(output_cost, 6),
            'total_cost_usd': round(total_cost, 6)
        }
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating Gemini cost: {e}. Tokens: prompt={prompt_tokens}, completion={completion_tokens}")
        return {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'input_cost_usd': 0.0,
            'output_cost_usd': 0.0,
            'total_cost_usd': 0.0
        }


# --- Unified LLM Client ---
AI_MODE = os.getenv("AI_MODE", "real").lower()  # "real" or "stub" for local testing


class Gemini3Client:
    """Gemini 3 client with token + cost tracking."""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.model_name = GEMINI3_MODEL or "models/gemini-3.0-pro-exp-01"
        self.default_max_tokens = int(os.getenv("GEMINI3_MAX_OUTPUT_TOKENS", "65000"))
        self.model = None
        if GEMINI_API_KEY and AI_MODE != "stub":
            try:
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                logger.error(f"Error initializing Gemini model '{self.model_name}': {e}")
                self.model = None
    
    async def generate(self, system: str, user: str, max_output_tokens: int, temperature: float, call_label: str) -> str:
        self.call_count += 1
        logger.info(f"[{call_label}] Starting Gemini call #{self.call_count}")
        logger.info(f"[{call_label}] System prompt length: {len(system)} chars")
        logger.info(f"[{call_label}] User content length: {len(user)} chars")
        max_tokens = max_output_tokens or self.default_max_tokens
        logger.info(f"[{call_label}] max_output_tokens set to {max_tokens}")
        
        if AI_MODE == "stub":
            logger.info(f"[{call_label}] AI_MODE=stub: Returning stub response")
            stub_response = f"[STUB GEMINI RESPONSE for {call_label}] System: {system[:120]}... User: {user[:120]}..."
            self.total_prompt_tokens += len(system.split()) + len(user.split())
            self.total_completion_tokens += len(stub_response.split())
            return stub_response
        
        if not GEMINI_API_KEY:
            logger.error(f"[{call_label}] GEMINI_API_KEY not configured - cannot call Gemini 3")
            raise Exception("Gemini API key not configured")
        
        if self.model is None:
            try:
                self.model = genai.GenerativeModel(self.model_name)
            except Exception as e:
                logger.error(f"[{call_label}] Failed to initialize Gemini model '{self.model_name}': {e}")
                raise
        
        prompt_sections = []
        if system:
            prompt_sections.append(f"[SYSTEM INSTRUCTIONS]\n{system.strip()}")
        prompt_sections.append(f"[USER INPUT]\n{user.strip()}")
        combined_prompt = "\n\n".join(prompt_sections)
        
        try:
            logger.info(f"[{call_label}] Calling Gemini model '{self.model_name}'...")
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            response = await self.model.generate_content_async(
                combined_prompt,
                generation_config=generation_config
            )
            logger.info(f"[{call_label}] Gemini API call completed successfully")
        except Exception as e:
            logger.error(f"[{call_label}] Gemini API error: {e}", exc_info=True)
            raise
        
        usage_metadata = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            try:
                usage_metadata = {
                    'prompt_tokens': int(getattr(response.usage_metadata, 'prompt_token_count', 0) or 0),
                    'completion_tokens': int(getattr(response.usage_metadata, 'candidates_token_count',
                                                     getattr(response.usage_metadata, 'completion_token_count', 0)) or 0),
                    'total_tokens': int(getattr(response.usage_metadata, 'total_token_count', 0) or 0)
                }
                logger.info(f"[{call_label}] Token usage - Input: {usage_metadata['prompt_tokens']}, Output: {usage_metadata['completion_tokens']}, Total: {usage_metadata['total_tokens']}")
            except Exception as meta_error:
                logger.warning(f"[{call_label}] Failed to parse Gemini usage metadata: {meta_error}")
                usage_metadata = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        self.total_prompt_tokens += usage_metadata['prompt_tokens']
        self.total_completion_tokens += usage_metadata['completion_tokens']
        call_cost = calculate_gemini3_cost(usage_metadata['prompt_tokens'], usage_metadata['completion_tokens'])
        self.total_cost_usd += call_cost['total_cost_usd']
        logger.info(f"[{call_label}] Call cost: ${call_cost['total_cost_usd']:.6f} (Input: ${call_cost['input_cost_usd']:.6f}, Output: ${call_cost['output_cost_usd']:.6f})")
        
        response_text = ""
        if hasattr(response, 'text') and response.text:
            response_text = response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            for candidate in response.candidates:
                if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                    part_texts = [getattr(part, "text", "") for part in candidate.content.parts]
                    response_text = " ".join(part_texts).strip()
                    if response_text:
                        break
        if not response_text:
            logger.error(f"[{call_label}] Gemini response empty or blocked")
            raise Exception("Gemini response was empty or blocked")
        
        logger.info(f"[{call_label}] Response length: {len(response_text)} characters")
        return response_text
    
    def get_summary(self) -> dict:
        return {
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_prompt_tokens + self.total_completion_tokens,
            'total_cost_usd': self.total_cost_usd,
            'call_count': self.call_count
        }


def _blueprint_to_json(blueprint: Dict[str, Any]) -> str:
    if blueprint.get("parsed"):
        return json.dumps(blueprint['parsed'].model_dump(by_alias=True), indent=2)
    return blueprint.get("raw_text", "")


async def g0_global_blueprint(llm: Gemini3Client, serialized_chart: dict, chart_summary: str, unknown_time: bool) -> Dict[str, Any]:
    """Gemini Call 0 - produce JSON planning blueprint."""
    system_prompt = """You are a master true sidereal planning intelligence. Output ONLY JSON. No markdown or commentary outside the JSON object.
Schema (all keys required):
- life_thesis: string paragraph
- core_axes: list of 3-4 objects {name, description, chart_factors[], immature_expression, mature_expression}
- top_themes: list of 5 {label, text}
- sun_moon_ascendant_plan: list of {body, sidereal_expression, tropical_expression, integration_notes}
- planetary_clusters: list of {name, members[], description, implications}
- houses_by_domain: list of {domain, summary, indicators[]}
- aspect_highlights: list of {title, aspect, meaning, life_applications[]}
- patterns: list of {name, description, involved_points[]}
- themed_chapters: list of {chapter, thesis, subtopics[], supporting_factors[]}
- shadow_contradictions: list of {tension, drivers[], integration_strategy}
- growth_edges: list of {focus, description, practices[]}
- final_principles_and_prompts: {principles[], prompts[]}
- snapshot: short planning notes highlighting the contradictions, drives, social patterns, shadow, and high-expression arc to emphasize in the Snapshot section
All notes must be concise and cite specific chart factors (sidereal/tropical placements, aspects, nodes, numerology, dominant patterns)."""
    
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "Birth time is UNKNOWN. Avoid relying on houses/angles; focus on sign-level, planetary, and aspect evidence." if unknown_time else "Birth time is known. Houses and angles are available."
    user_prompt = f"""Chart Summary:
{chart_summary}

Serialized Chart Data:
{serialized_chart_json}

Context:
- {time_note}
- Plan the entire premium reading. You are not writing prose sections yet—only outlining with analytic notes.
- Use short, information-dense strings that reference the exact placements/aspects backing each note.
- The snapshot field should capture the most intimate contradictions, motivations, relational behaviors, and shadow/high-expression arcs you observe so the writer can produce the required 300–500 word section later.

Return ONLY the JSON object."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=12000,
        temperature=0.2,
        call_label="G0_global_blueprint"
    )
    
    blueprint_parsed = parse_json_response(response_text, GlobalReadingBlueprint)
    if blueprint_parsed:
        logger.info("G0 parsed blueprint successfully")
        return {"parsed": blueprint_parsed, "raw_text": response_text}
    
    logger.warning("G0 blueprint parsing failed - returning raw JSON text fallback")
    return {"parsed": None, "raw_text": response_text}


async def g1_natal_foundation(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """Gemini Call 1 - Natal foundations + personal/social planets."""
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "After the Snapshot, include a short 'What We Know / What We Don't Know' paragraph clarifying birth time is unknown. Avoid houses/angles entirely." if unknown_time else "You may cite houses and angles explicitly."
    
    system_prompt = """You are The Synthesizer, an expert true sidereal astrologer.
Tone: psychologically literate consultant, clinical but warm, concrete, second person, confident but non-absolute.
Scope for this call ONLY:
- Cover & Orientation
- Snapshot (7 bullets)
- Chart Overview & Core Themes (strict structure)
- Foundational Pillars: Sun, Moon, Ascendant
- Personal & Social Planets (Mercury through Saturn)
- Houses & Life Domains summary
Rules:
- Follow the blueprint exactly—do not invent placements.
- Trace every statement back to explicit chart factors (sidereal vs tropical contrasts, nodes, numerology, dominant elements/patterns).
- No fluff or repetition. Build depth quickly."""
    
    heading_block = "   WHAT WE KNOW / WHAT WE DON'T KNOW\n" if unknown_time else ""
    
    snapshot_notes = ""
    if blueprint.get("parsed") and getattr(blueprint['parsed'], "snapshot", None):
        snapshot_notes = blueprint['parsed'].snapshot
    elif blueprint.get("raw_text"):
        snapshot_notes = "Snapshot planning notes were not parsed; rely on the chart summary and SNAPSHOT_PROMPT."
    
    user_prompt = f"""[CHART SUMMARY]\n{chart_summary}\n
[SERIALIZED CHART DATA]\n{serialized_chart_json}\n
[BLUEPRINT JSON]\n{blueprint_json}\n
Instructions:
1. Use uppercase headings in this order:
   COVER & ORIENTATION
   SNAPSHOT: WHAT WILL FEEL MOST TRUE ABOUT YOU
{heading_block}   CHART OVERVIEW & CORE THEMES
   FOUNDATIONAL PILLARS: SUN - MOON - ASCENDANT
   PERSONAL & SOCIAL PLANETS
   HOUSES & LIFE DOMAINS SUMMARY
2. Follow this brief for the Snapshot section (use it verbatim):
{SNAPSHOT_PROMPT.strip()}

Blueprint notes for Snapshot (use them to prioritize chart factors):
{snapshot_notes}
3. Chart Overview & Core Themes: obey the existing specification (5 themes, each with heading `Theme 1 – [Title]`, 2 headline sentences, `Why this shows up in your chart`, `How it tends to feel and play out`). At least 2 themes must highlight Sidereal vs Tropical contrasts; at least 1 integrates Nodes. Use numerology only when reinforcing.
4. Foundational Pillars: use sun_moon_ascendant_plan to craft two dense paragraphs per body (internal process + external expression).
5. Personal & Social Planets:
   - Mercury, Venus, Mars → cognition/communication, relating/attraction, drive/assertion. Include concrete examples.
   - Jupiter, Saturn → expansion vs discipline interplay with real-life scenarios.
6. Houses & Life Domains: synthesize houses_by_domain (skip houses entirely if unknown time). {time_note}
7. Reference planetary_clusters, aspect_highlights, and patterns when relevant.
8. Keep Action Checklist for later sections (do NOT include here)."""
    
    return await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=45000,
        temperature=0.7,
        call_label="G1_natal_foundation"
    )


async def g2_deep_dive_chapters(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    natal_sections: str,
    unknown_time: bool
) -> str:
    """Gemini Call 2 - Themed chapters, aspects, shadow, owner's manual."""
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    
    system_prompt = """You are continuing the same reading. 
Scope for this call:
- LOVE, RELATIONSHIPS & ATTACHMENT
- WORK, MONEY & VOCATION
- EMOTIONAL LIFE, FAMILY & HEALING
- SPIRITUAL PATH & MEANING
- MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS
- SHADOW, CONTRADICTIONS & GROWTH EDGES
- OWNER'S MANUAL: FINAL INTEGRATION
Guardrails:
- Read the earlier sections (provided) so you do not contradict prior content.
- Use blueprint.themed_chapters, aspect_highlights, patterns, shadow_contradictions, growth_edges, and final_principles_and_prompts.
- Every paragraph must include at least one concrete scenario or behavioral example.
- Maintain the clinical-but-warm tone."""
    
    user_prompt = f"""[CHART SUMMARY]\n{chart_summary}\n
[SERIALIZED CHART DATA]\n{serialized_chart_json}\n
[BLUEPRINT JSON]\n{blueprint_json}\n
[PRIOR SECTIONS ALREADY WRITTEN]\n{natal_sections}\n
Section instructions:
LOVE, RELATIONSHIPS & ATTACHMENT
- Use Venus, Mars, Nodes, Juno, 5th/7th houses (if time known) plus relevant aspects/patterns.
- Provide 2-3 concrete relational dynamics + guidance.

WORK, MONEY & VOCATION
- Integrate Midheaven/10th/2nd houses when available, Saturn/Jupiter signatures, dominant elements, numerology if reinforcing.

EMOTIONAL LIFE, FAMILY & HEALING
- Moon aspects, 4th/8th/12th houses, Chiron, blueprint emotional chapter notes.

SPIRITUAL PATH & MEANING
- Nodes, Neptune, Pluto, numerology, blueprint spiritual chapter.

MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS
- For each blueprint.aspect_highlights entry, deliver:
   * Core tension/strength statement
   * Why it exists (placements/aspects)
   * One real-life example
- Summarize blueprint.patterns afterwards (Grand Trines, T-Squares, Stelliums, Yods, etc.).

SHADOW, CONTRADICTIONS & GROWTH EDGES
- For each blueprint.shadow_contradictions item, describe the tension, identify drivers, provide integration strategy.
- Weave blueprint.growth_edges as actionable experiments.

OWNER'S MANUAL: FINAL INTEGRATION
- Present 3-4 guiding principles plus the prompts from blueprint.final_principles_and_prompts.
- End with ACTION CHECKLIST (7 bullets) referencing earlier content.

Unknown time handling: {'Do NOT cite houses/angles; speak in terms of domains, signs, and aspects.' if unknown_time else 'You may cite houses/angles explicitly.'}
Ensure everything builds on prior sections rather than repeating them verbatim."""
    
    return await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=45000,
        temperature=0.7,
        call_label="G2_deep_dive_chapters"
    )


async def g3_polish_full_reading(
    llm: Gemini3Client,
    full_draft: str,
    chart_summary: str
) -> str:
    """Gemini Call 3 - polish entire reading."""
    system_prompt = """You are an editorial finisher.
Goals:
- Improve clarity, transitions, and rhythm.
- Remove redundancy and tighten sentences.
- Preserve all section headings, bullet counts, and astrological facts.
- Maintain tone (psychologically literate consultant, second person, confident but not absolute)."""
    
    user_prompt = f"""Full draft to polish:
{full_draft}

Reference chart summary (for context only, do not restate):
{chart_summary}

Return the polished reading with identical structure and headings."""
    
    return await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=65000,
        temperature=0.4,
        call_label="G3_polish_full_reading"
    )


async def get_gemini3_reading(chart_data: dict, unknown_time: bool) -> str:
    """Four-call Gemini 3 pipeline."""
    if not GEMINI_API_KEY and AI_MODE != "stub":
        logger.error("Gemini API key not configured - AI reading unavailable")
        raise Exception("Gemini API key not configured. AI reading is unavailable.")
    
    logger.info("="*60)
    logger.info("Starting Gemini 3 reading generation...")
    logger.info(f"AI_MODE: {AI_MODE}")
    logger.info(f"Unknown time: {unknown_time}")
    logger.info("="*60)
    
    llm = Gemini3Client()
    
    try:
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=unknown_time)
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
        
        blueprint = await g0_global_blueprint(llm, serialized_chart, chart_summary, unknown_time)
        natal_sections = await g1_natal_foundation(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        deep_sections = await g2_deep_dive_chapters(llm, serialized_chart, chart_summary, blueprint, natal_sections, unknown_time)
        full_draft = f"{natal_sections}\n\n{deep_sections}"
        final_reading = await g3_polish_full_reading(llm, full_draft, chart_summary)
        
        summary = llm.get_summary()
        cost_info = calculate_gemini3_cost(summary['total_prompt_tokens'], summary['total_completion_tokens'])
        
        logger.info("=== GEMINI 3 API COST SUMMARY ===")
        logger.info(f"Total Calls: {summary['call_count']}")
        logger.info(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        logger.info(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info(f"Input Cost: ${cost_info['input_cost_usd']:.6f}")
        logger.info(f"Output Cost: ${cost_info['output_cost_usd']:.6f}")
        logger.info(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f}")
        logger.info("=" * 50)
        
        print(f"\n{'='*60}")
        print("GEMINI 3 API COST SUMMARY")
        print(f"Total Calls: {summary['call_count']}")
        print(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print(f"Input Cost: ${cost_info['input_cost_usd']:.6f}")
        print(f"Output Cost: ${cost_info['output_cost_usd']:.6f}")
        print(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f}")
        print(f"{'='*60}\n")
        
        return final_reading
    except Exception as e:
        logger.error(f"Error during Gemini 3 reading generation: {e}", exc_info=True)
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")


def _sign_from_position(pos: str | None) -> str | None:
    """Extract sign from a position string like '12°34' Virgo'."""
    if not pos or pos == "N/A":
        return None
    parts = pos.split()
    return parts[-1] if parts else None


def get_quick_highlights(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate quick highlights from chart data without using AI.
    Returns a plain text string with bullet points about key chart features.
    """
    # Prepare lookups
    s_pos = {p["name"]: p for p in chart_data.get("sidereal_major_positions", [])}
    t_pos = {p["name"]: p for p in chart_data.get("tropical_major_positions", [])}
    s_extra = {p["name"]: p for p in chart_data.get("sidereal_additional_points", [])}
    t_extra = {p["name"]: p for p in chart_data.get("tropical_additional_points", [])}
    s_analysis = chart_data.get("sidereal_chart_analysis", {}) or {}
    t_analysis = chart_data.get("tropical_chart_analysis", {}) or {}
    numerology = chart_data.get("numerology_analysis", {}) or {}
    
    lines = []
    
    # Identity triad line (Sun, Moon, Asc)
    sun_s = _sign_from_position(s_pos.get("Sun", {}).get("position"))
    sun_t = _sign_from_position(t_pos.get("Sun", {}).get("position"))
    moon_s = _sign_from_position(s_pos.get("Moon", {}).get("position"))
    moon_t = _sign_from_position(t_pos.get("Moon", {}).get("position"))
    
    if not unknown_time:
        asc_s = _sign_from_position(s_pos.get("Ascendant", {}).get("position"))
        asc_t = _sign_from_position(t_pos.get("Ascendant", {}).get("position"))
    else:
        asc_s = asc_t = None
    
    headline_parts = []
    if sun_s:
        headline_parts.append(f"Sidereal Sun in {sun_s}")
    if sun_t:
        headline_parts.append(f"Tropical Sun in {sun_t}")
    if moon_s:
        headline_parts.append(f"Sidereal Moon in {moon_s}")
    if moon_t:
        headline_parts.append(f"Tropical Moon in {moon_t}")
    if not unknown_time and asc_s:
        headline_parts.append(f"Sidereal Ascendant in {asc_s}")
    if not unknown_time and asc_t:
        headline_parts.append(f"Tropical Ascendant in {asc_t}")
    
    if headline_parts:
        lines.append(" • " + " | ".join(headline_parts))
    
    # Dominant element & planet
    dom_elem_s = s_analysis.get("dominant_element")
    dom_planet_s = s_analysis.get("dominant_planet")
    
    if dom_elem_s or dom_planet_s:
        text = "You have a strong "
        if dom_elem_s:
            text += dom_elem_s.lower() + " emphasis"
        if dom_elem_s and dom_planet_s:
            text += " and a "
        if dom_planet_s:
            text += f"{dom_planet_s} signature"
        text += ", which shapes how you instinctively move through life."
        lines.append(" • " + text)
    
    # Nodal / life direction headline
    nn_pos = s_pos.get("True Node", {}) or {}
    nn_sign = _sign_from_position(nn_pos.get("position"))
    
    if nn_sign:
        lines.append(
            f" • Your Sidereal North Node in {nn_sign} points to a lifetime of growing into the qualities of that sign."
        )
    
    # Numerology quick hook
    life_path = numerology.get("life_path_number")
    if life_path:
        lines.append(
            f" • Life Path {life_path} adds a repeating lesson about how you define success and meaning in this life."
        )
    
    # One or two strongest aspects
    aspects = chart_data.get("sidereal_aspects", []) or []
    if aspects:
        def _parse_aspect_score(score_val):
            """Convert score string to float."""
            if isinstance(score_val, (int, float)):
                return float(score_val)
            if isinstance(score_val, str):
                try:
                    return float(score_val)
                except (ValueError, TypeError):
                    return 0.0
            return 0.0
        
        def _parse_aspect_orb(orb_val):
            """Convert orb string (e.g., '2.34°') to float."""
            if isinstance(orb_val, (int, float)):
                return abs(float(orb_val))
            if isinstance(orb_val, str):
                try:
                    # Remove degree symbol and any whitespace, then convert
                    orb_clean = orb_val.replace('°', '').strip()
                    return abs(float(orb_clean))
                except (ValueError, TypeError):
                    return 999.0
            return 999.0
        
        aspects_sorted = sorted(
            aspects,
            key=lambda a: (-_parse_aspect_score(a.get("score", 0)), _parse_aspect_orb(a.get("orb", 999)))
        )
        top_aspects = aspects_sorted[:2]
        
        for a in top_aspects:
            p1 = a.get("p1_name", "Body 1")
            p2 = a.get("p2_name", "Body 2")
            atype = a.get("type", "aspect")
            atype_lower = atype.lower() if atype else ""
            
            if atype_lower in ("conjunction", "trine", "sextile"):
                vibe = "natural talent or ease"
            elif atype_lower in ("square", "opposition"):
                vibe = "core tension you are learning to work with"
            else:
                vibe = "distinct pattern in your personality"
            
            lines.append(
                f" • {p1} {atype} {p2} marks a {vibe} that keeps showing up across your life."
            )
    
    # Fallback if nothing available
    if not lines:
        return "Quick highlights are unavailable for this chart."
    
    # Return final text
    intro = "Quick Highlights From Your Chart"
    body = "\n".join(lines)
    return f"{intro}\n{body}"


# --- Three-Call Reading Generation Functions ---

async def call1_chart_overview_and_themes(llm: Gemini3Client, serialized_chart: dict, chart_summary: str, 
                                         unknown_time: bool) -> dict:
    """
    Call 1: Generate structured chart overview and core themes.
    Returns parsed JSON structure.
    
    This call uses Claude's JSON mode to ensure structured output.
    """
    logger.info("="*60)
    logger.info("CALL 1: Chart Overview and Core Themes")
    logger.info("="*60)
    
    system_prompt = """You are an expert true sidereal astrologer and structural planner. Your job in this call is ONLY to analyze the chart and output a clean JSON plan for the reading (no prose, no commentary).

**Zodiac Definitions:**
- The **Sidereal** placements represent the soul's deeper karmic blueprint, innate spiritual gifts, and ultimate life purpose.
- The **Tropical** placements represent the personality's expression, psychological patterns, and how the soul's purpose manifests in this lifetime.

**Your Task:**
Analyze the chart data to identify exactly 5 core themes. For each theme, provide:
1. A short title in plain language
2. Exactly 2 headline sentences that clearly name the pattern
3. A "why_in_chart" section (2-4 sentences) referencing specific placements/aspects
4. A "how_it_plays_out" section (1-2 concrete real-life examples)

When choosing the 5 themes, prioritize:
- Themes involving Sun, Moon, Ascendant (if known), or Nodes
- Themes where Sidereal and Tropical placements sharply contrast
- Themes supported by multiple signals (element + planet + numerology)

**CRITICAL: You must output ONLY valid JSON matching this exact schema. The entire response must be a single valid JSON object with no extra text, no markdown, no code blocks, no explanations. Start your response with {{ and end with }}.**

{
  "themes": [
    {
      "title": "Short Title in Plain Language",
      "headline_sentences": [
        "First headline sentence",
        "Second headline sentence"
      ],
      "why_in_chart": {
        "text": "2-4 sentences explaining why this shows up, referencing specific placements/aspects"
      },
      "how_it_plays_out": {
        "text": "1-2 concrete real-life examples of how this tends to feel and play out"
      }
    }
  ],
  "synthesis": {
    "text": "Paragraph showing how the 5 themes interact",
    "key_tension": "One key inner tension (e.g., 'between security and risk')",
    "growth_direction": "Key long-term growth direction from resolving the tension"
  }
}

**IMPORTANT:** Your response must be valid JSON that can be parsed by json.loads(). Do not include any text before or after the JSON object. Do not wrap it in markdown code blocks."""
    
    user_prompt = f"""**Chart Data:**
{chart_summary}

**Note:** {"Birth time is unknown, so house placements and Ascendant/MC are unavailable." if unknown_time else "Full chart data including houses and angles is available."}

**Output Requirement:** Return ONLY the JSON object described in the system prompt. Your response must start with {{ and end with }}. No markdown, no explanations, no code blocks, no text outside the JSON object."""
    
    # Generate JSON response - Claude will follow the strict JSON instructions in the prompt
    # Note: Claude doesn't support OpenAI-style response_format parameter
    # We rely on strong prompting to ensure JSON output
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8192,  # Maximum for comprehensive readings
        call_label="call1_chart_overview_and_themes"
    )
    
    # Parse JSON response
    chart_overview_output = parse_json_response(response_text, ChartOverviewOutput)
    if chart_overview_output is None:
        logger.warning("Failed to parse call1 JSON response, using raw text")
        # Return a dict structure for compatibility
        return {"raw_text": response_text, "parsed": None}
    
    logger.info("Call 1 completed successfully - parsed JSON structure")
    return {"raw_text": response_text, "parsed": chart_overview_output}


async def call2_full_section_drafts(llm: Gemini3Client, serialized_chart: dict, chart_summary: str,
                                   chart_overview: dict, unknown_time: bool) -> str:
    """
    Call 2: Generate full draft of all reading sections.
    Uses chart_overview from call1 as structured context.
    
    This call generates the full reading draft following the JSON plan from Call 1.
    """
    logger.info("="*60)
    logger.info("CALL 2: Full Section Drafts")
    logger.info("="*60)
    
    # Prepare structured overview context (JSON blueprint from Call 1)
    overview_context = ""
    if chart_overview.get("parsed"):
        overview_context = f"""
**STRUCTURED CHART OVERVIEW (Use this as primary source for Chart Overview section):**
{json.dumps(chart_overview['parsed'].model_dump(), indent=2)}
"""
    elif chart_overview.get("raw_text"):
        overview_context = f"""
**CHART OVERVIEW (Text Format):**
{chart_overview['raw_text']}
"""
    
    system_prompt = """You are an expert true sidereal astrologer writing a deeply personalized reading. Follow the supplied JSON plan exactly. Do not change structure, only fill in the content.

You are The Synthesizer, an insightful astrological consultant who excels at weaving complex data into a clear and compelling narrative. Your skill is in explaining complex astrological data in a practical and grounded way.

Tone Guidelines:
- Sound like a psychologically literate consultant speaking to an intelligent client.
- Favor clear, concrete language over mystical phrasing.
- Use second person ("you") throughout.
- Avoid hedging like "you might possibly"; prefer confident but non-absolute phrases such as "you tend to" or "you are likely to."

**CRITICAL RULE:** Base your reading *only* on the analysis provided. Do not invent any placements, planets, signs, or aspects that are not explicitly listed."""
    
    user_prompt = f"""**Chart Data Summary:**
{chart_summary}

{overview_context}

**Your Task:**
Write a comprehensive analysis. Structure your response exactly as follows, using plain text headings without markdown.

**Snapshot: What Will Feel Most True About You**
(Open the reading with 7 short bullet points. Each bullet must describe a concrete trait or pattern someone who knows this person well would instantly recognize. Avoid astrological jargon; speak directly to the reader in plain psychological/behavioral language using "you." These bullets should feel specific and uncanny, not generic.)

{"After the Snapshot, include a short 4 sentence paragraph that explains the birth time is unknown, so the interpretation focuses on sign-level and aspect-level patterns rather than precise houses or angles. Reassure the reader that the core psychological and karmic signatures remain accurate despite missing timing data. Keep this framing brief and non-technical." if unknown_time else ""}

**Chart Overview and Core Themes**
{"Use the structured chart overview provided above to write this section. Expand each theme with the exact structure requested: Theme heading, 2 headline sentences, 'Why this shows up in your chart:' subsection, and 'How it tends to feel and play out:' subsection. End with the synthesis paragraph." if chart_overview.get("parsed") else "(Under this heading, write an in-depth interpretive introduction. Focus on clarity, depth, and insight—not just listing placements. Your job is to make the client feel 'seen' in a way that is traceable back to the chart. Identify exactly 5 core psychological or life themes. Structure each theme as: Theme heading, 2 headline sentences, 'Why this shows up in your chart:' subsection, and 'How it tends to feel and play out:' subsection. End with a synthesis paragraph.)"}

**Your Astrological Blueprint: Planets, Points, and Angles**
(Under this heading, provide detailed analysis for each major planet and point. For each body, write 3 paragraphs: Sidereal Interpretation, Tropical Interpretation, and Synthesis. Group them thematically: Luminaries (Sun, Moon), Personal Planets (Mercury, Venus, Mars), Generational Planets (Jupiter, Saturn, Uranus, Neptune, Pluto), {"Nodes (True Node, South Node), Major Asteroids (Chiron, Ceres, Pallas, Juno, Vesta, Lilith)." if unknown_time else "Angles (Ascendant, Descendant, Midheaven, Imum Coeli), Nodes (True Node, South Node), Major Asteroids (Chiron, Ceres, Pallas, Juno, Vesta, Lilith), Other Points (Part of Fortune, Vertex)."} {"Remember: Do not mention houses, Ascendant, MC, or Chart Ruler as birth time is unknown." if unknown_time else ""})

**Major Life Dynamics: The Tightest Aspects**
(Under this heading, analyze the top 8 tightest aspects in the Sidereal chart. For each aspect, write a detailed paragraph explaining the core tension, strength, or pattern in plain language, and include at least one concrete example of how this energy might show up in real life.)

**Summary and Key Takeaways**
(Under this heading, write a practical, empowering conclusion that summarizes the most important takeaways from the chart. Offer guidance on key areas for personal growth and self-awareness. Close this section with a short "Action Checklist" containing 7 bullet points. Each bullet must point to a concrete focus area or experiment that clearly connects back to themes/aspects discussed above. Avoid generic self-help cliches.)"""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.7,
        max_output_tokens=8192,  # Allow longer output for full reading
        call_label="call2_full_section_drafts"
    )
    
    logger.info("Call 2 completed successfully")
    return response_text


async def call3_polish_reading(llm: Gemini3Client, draft_reading: str, chart_summary: str) -> str:
    """
    Call 3: Polish the full draft reading for clarity and impact.
    
    This is a lightweight polish pass that improves tone, flow, and clarity
    without changing meaning or adding new interpretations.
    """
    logger.info("="*60)
    logger.info("CALL 3: Polish Reading")
    logger.info("="*60)
    
    system_prompt = """You are a careful editor. You will polish tone, flow, and clarity without changing meaning or adding new interpretations. Keep all section headings and structure identical.

Style guide:
- Warm, grounded, psychologically insightful
- No fluff, no fatalism
- Clear and concrete language
- Maintain the exact structure and headings from the draft"""
    
    user_prompt = f"""**Draft Reading to Polish:**
{draft_reading}

**Your Task:**
Review and polish this reading. Make improvements to:
- Sentence flow and transitions
- Clarity of explanations
- Consistency of tone
- Impact of key insights

**CRITICAL:** Do NOT change:
- The structure or section headings
- The factual astrological content
- The number of themes, bullets, or examples
- Any specific placements, aspects, or chart data mentioned

Output the polished reading with the exact same structure as the draft."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        temperature=0.3,  # Lower temperature for polishing
        max_output_tokens=8192,  # Allow longer output
        call_label="call3_polish_reading"
    )
    
    logger.info("Call 3 completed successfully")
    return response_text


# --- Email Functions ---

# Removed format_full_report_for_email - now using PDF generation instead


def send_chart_email_via_sendgrid(pdf_bytes: bytes, recipient_email: str, subject: str, chart_name: str):
    """Send email with PDF attachment using SendGrid API."""
    from datetime import datetime
    
    # Create log file path
    log_file_path = "sendgrid_connection.log"
    
    def write_to_log(message: str, is_error: bool = False):
        """Write message to both logger and log file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        logger.info(message) if not is_error else logger.error(message)
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as log_error:
            logger.error(f"Failed to write to log file: {log_error}")
    
    write_to_log("="*60)
    write_to_log("SendGrid Email Sending Attempt")
    write_to_log("="*60)
    
    if not SENDGRID_API_KEY:
        error_msg = "SendGrid API key not configured. Cannot send email."
        write_to_log(error_msg, is_error=True)
        write_to_log(f"  SENDGRID_API_KEY value: {SENDGRID_API_KEY}")
        write_to_log(f"  SENDGRID_API_KEY length: {len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 0}")
        return False
    
    if not SENDGRID_FROM_EMAIL:
        error_msg = "SendGrid FROM email not configured. Cannot send email."
        write_to_log(error_msg, is_error=True)
        write_to_log(f"  SENDGRID_FROM_EMAIL value: {SENDGRID_FROM_EMAIL}")
        return False
    
    write_to_log(f"SendGrid Configuration Check:")
    write_to_log(f"  API Key present: Yes (length: {len(SENDGRID_API_KEY)} characters)")
    write_to_log(f"  From Email: {SENDGRID_FROM_EMAIL}")
    write_to_log(f"  To Email: {recipient_email}")
    write_to_log(f"  Subject: {subject}")
    write_to_log(f"  Chart name: {chart_name}")
    write_to_log(f"  PDF size: {len(pdf_bytes)} bytes")

    try:
        # Create email message
        write_to_log("Creating email message object...")
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=recipient_email,
            subject=subject,
            html_content=f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Your Astrology Chart Report</h2>
                <p>Dear {chart_name},</p>
                <p>Thank you for using Synthesis Astrology. Your complete astrological chart report is attached as a PDF.</p>
                <p>The PDF includes:</p>
                <ul>
                    <li>Your natal chart wheels (Sidereal and Tropical)</li>
                    <li>Your complete AI Astrological Synthesis</li>
                    <li>Full astrological data and positions</li>
                </ul>
                <p>We hope this report provides valuable insights into your personality, life patterns, and spiritual growth.</p>
                <p>Best regards,<br>Synthesis Astrology<br><a href="https://synthesisastrology.com" style="color: #1b6ca8;">synthesisastrology.com</a></p>
            </body>
            </html>
            """
        )
        write_to_log("Email message object created successfully")
        
        # Attach PDF
        write_to_log("Encoding PDF attachment...")
        encoded_pdf = base64.b64encode(pdf_bytes).decode()
        attachment = Attachment(
            FileContent(encoded_pdf),
            FileName(f"Astrology_Report_{chart_name.replace(' ', '_')}.pdf"),
            FileType('application/pdf'),
            Disposition('attachment')
        )
        message.add_attachment(attachment)
        write_to_log(f"PDF attachment added (encoded size: {len(encoded_pdf)} characters)")
        
        # Initialize SendGrid client
        write_to_log("Initializing SendGrid client...")
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            write_to_log("SendGrid client initialized successfully")
        except Exception as init_error:
            error_msg = f"Failed to initialize SendGrid client: {type(init_error).__name__}: {init_error}"
            write_to_log(error_msg, is_error=True)
            import traceback
            write_to_log(f"Initialization traceback: {traceback.format_exc()}", is_error=True)
            return False
        
        # Attempt to send email
        write_to_log("Attempting to send email via SendGrid API...")
        try:
            response = sg.send(message)
            write_to_log(f"SendGrid API call completed")
            write_to_log(f"Response status code: {response.status_code}")
            
            # Log response details
            if hasattr(response, 'headers'):
                write_to_log(f"Response headers: {dict(response.headers)}")
            if hasattr(response, 'body'):
                try:
                    if isinstance(response.body, bytes):
                        response_body = response.body.decode('utf-8')
                    else:
                        response_body = str(response.body)
                    write_to_log(f"Response body: {response_body[:500]}")  # First 500 chars
                except Exception as decode_error:
                    write_to_log(f"Could not decode response body: {decode_error}")
            
            if response.status_code in [200, 202]:
                success_msg = f"Email with PDF sent successfully via SendGrid to {recipient_email} (status: {response.status_code})"
                write_to_log(success_msg)
                write_to_log("="*60)
                return True
            else:
                # Get response body properly - SendGrid response has body as bytes
                try:
                    if hasattr(response, 'body'):
                        if isinstance(response.body, bytes):
                            response_body = response.body.decode('utf-8')
                        else:
                            response_body = str(response.body)
                    else:
                        response_body = f"No body attribute. Response: {response}"
                except Exception as decode_error:
                    response_body = f"Error decoding response body: {decode_error}. Response object: {response}"
                
                error_msg = f"SendGrid returned non-success status: {response.status_code}"
                write_to_log(error_msg, is_error=True)
                write_to_log(f"SendGrid response body: {response_body}", is_error=True)
                write_to_log(f"SendGrid response headers: {getattr(response, 'headers', 'N/A')}", is_error=True)
                write_to_log("="*60)
                return False
                
        except Exception as send_error:
            error_msg = f"Exception during SendGrid send() call: {type(send_error).__name__}: {send_error}"
            write_to_log(error_msg, is_error=True)
            import traceback
            write_to_log(f"Send error traceback: {traceback.format_exc()}", is_error=True)
            write_to_log("="*60)
            return False
            
    except Exception as e:
        error_msg = f"Error sending email via SendGrid to {recipient_email}: {type(e).__name__}: {e}"
        write_to_log(error_msg, is_error=True)
        import traceback
        write_to_log(f"Full traceback: {traceback.format_exc()}", is_error=True)
        write_to_log("="*60)
        return False


async def generate_reading_and_send_email(chart_data: Dict, unknown_time: bool, user_inputs: Dict):
    """Background task to generate reading and send emails with PDF attachments."""
    try:
        logger.info("="*60)
        logger.info("Starting background task for reading generation and email sending.")
        logger.info("="*60)
        chart_name = user_inputs.get('full_name', 'N/A')
        user_email = user_inputs.get('user_email')
        # Strip whitespace if email is provided
        if user_email and isinstance(user_email, str):
            user_email = user_email.strip() or None  # Convert empty string to None
        
        logger.info(f"Generating AI reading for: {chart_name}")
        
        # Generate the reading
        try:
            reading_text = await get_gemini3_reading(chart_data, unknown_time)
            logger.info(f"AI Reading successfully generated for: {chart_name} (length: {len(reading_text)} characters)")
            
            # Store reading in cache for frontend retrieval
            chart_hash = generate_chart_hash(chart_data, unknown_time)
            reading_cache[chart_hash] = {
                'reading': reading_text,
                'timestamp': datetime.now(),
                'chart_name': chart_name
            }
            logger.info(f"Reading stored in cache with hash: {chart_hash}")
        except Exception as e:
            logger.error(f"Error generating reading: {e}", exc_info=True)
            # Still try to send an error notification email if possible
            if user_email and SENDGRID_API_KEY and SENDGRID_FROM_EMAIL:
                try:
                    from sendgrid import SendGridAPIClient
                    from sendgrid.helpers.mail import Mail
                    error_message = Mail(
                        from_email=SENDGRID_FROM_EMAIL,
                        to_emails=user_email,
                        subject=f"Error Generating Your Astrology Report",
                        html_content=f"""
                        <html>
                        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                            <h2 style="color: #e53e3e;">Error Generating Report</h2>
                            <p>Dear {chart_name},</p>
                            <p>We encountered an error while generating your astrology reading. Please try again or contact support.</p>
                            <p>Error: {str(e)}</p>
                            <p>Best regards,<br>Synthesis Astrology<br><a href="https://synthesisastrology.com" style="color: #1b6ca8;">synthesisastrology.com</a></p>
                        </body>
                        </html>
                        """
                    )
                    sg = SendGridAPIClient(SENDGRID_API_KEY)
                    sg.send(error_message)
                    logger.info(f"Error notification email sent to {user_email}")
                except Exception as email_error:
                    logger.error(f"Failed to send error notification email: {email_error}")
            return
        
        logger.info(f"Email task - User email provided: {bool(user_email)}, Admin email configured: {bool(ADMIN_EMAIL)}")
        logger.info(f"SendGrid API key configured: {bool(SENDGRID_API_KEY)}, From email configured: {bool(SENDGRID_FROM_EMAIL)}")
        
        # Validate SendGrid configuration
        if not SENDGRID_API_KEY:
            error_msg = "❌ SENDGRID_API_KEY is not set. Cannot send emails. Please set this environment variable in Render."
            logger.error(error_msg)
            logger.error("="*60)
            return
        if not SENDGRID_FROM_EMAIL:
            error_msg = "❌ SENDGRID_FROM_EMAIL is not set. Cannot send emails. Please set this environment variable in Render."
            logger.error(error_msg)
            logger.error("="*60)
            return

        # Generate PDF report
        try:
            logger.info("Generating PDF report...")
            pdf_bytes = generate_pdf_report(chart_data, reading_text, user_inputs)
            logger.info(f"PDF generated successfully ({len(pdf_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            import traceback
            logger.error(f"PDF generation traceback: {traceback.format_exc()}")
            return  # Don't send emails if PDF generation fails

        # Send email to the user (if provided and not empty)
        if user_email:
            logger.info(f"Attempting to send email to user: {user_email}")
            email_sent = send_chart_email_via_sendgrid(
                pdf_bytes, 
                user_email, 
                f"Your Astrology Chart Report for {chart_name}",
                chart_name
            )
            if email_sent:
                logger.info(f"Email successfully sent to user: {user_email}")
            else:
                logger.warning(f"Failed to send email to user: {user_email}")
        else:
            logger.info("No user email provided, skipping user email.")
            
        # Send email to the admin (if configured)
        if ADMIN_EMAIL:
            logger.info(f"Attempting to send email to admin: {ADMIN_EMAIL}")
            email_sent = send_chart_email_via_sendgrid(
                pdf_bytes, 
                ADMIN_EMAIL, 
                f"New Chart Generated: {chart_name}",
                chart_name
            )
            if email_sent:
                logger.info(f"Email successfully sent to admin: {ADMIN_EMAIL}")
            else:
                logger.warning(f"Failed to send email to admin: {ADMIN_EMAIL}")
        else:
            logger.info("No admin email configured, skipping admin email.")
        
        logger.info(f"Background task completed for {chart_name}.")
    except Exception as e:
        logger.error(f"Error in background task: {e}", exc_info=True)


async def send_emails_in_background(chart_data: Dict, reading_text: str, user_inputs: Dict):
    """Background task to send emails with PDF attachments to user and admin."""
    try:
        logger.info("="*60)
        logger.info("Starting background task for email sending.")
        logger.info("="*60)
        user_email = user_inputs.get('user_email')
        # Strip whitespace if email is provided
        if user_email and isinstance(user_email, str):
            user_email = user_email.strip() or None  # Convert empty string to None
        chart_name = user_inputs.get('full_name', 'N/A')
        
        logger.info(f"Email task - User email provided: {bool(user_email)}, Admin email configured: {bool(ADMIN_EMAIL)}")
        logger.info(f"SendGrid API key configured: {bool(SENDGRID_API_KEY)}, From email configured: {bool(SENDGRID_FROM_EMAIL)}")
        
        # Validate SendGrid configuration
        if not SENDGRID_API_KEY:
            error_msg = "❌ SENDGRID_API_KEY is not set. Cannot send emails. Please set this environment variable in Render."
            logger.error(error_msg)
            logger.error("="*60)
            return
        if not SENDGRID_FROM_EMAIL:
            error_msg = "❌ SENDGRID_FROM_EMAIL is not set. Cannot send emails. Please set this environment variable in Render."
            logger.error(error_msg)
            logger.error("="*60)
            return

        # Generate PDF report
        try:
            logger.info("Generating PDF report...")
            pdf_bytes = generate_pdf_report(chart_data, reading_text, user_inputs)
            logger.info(f"PDF generated successfully ({len(pdf_bytes)} bytes)")
        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            import traceback
            logger.error(f"PDF generation traceback: {traceback.format_exc()}")
            return  # Don't send emails if PDF generation fails

        # Send email to the user (if provided and not empty)
        if user_email:
            logger.info(f"Attempting to send email to user: {user_email}")
            email_sent = send_chart_email_via_sendgrid(
                pdf_bytes, 
                user_email, 
                f"Your Astrology Chart Report for {chart_name}",
                chart_name
            )
            if email_sent:
                logger.info(f"Email successfully sent to user: {user_email}")
            else:
                logger.warning(f"Failed to send email to user: {user_email}")
        else:
            logger.info("No user email provided, skipping user email.")
            
        # Send email to the admin (if configured)
        if ADMIN_EMAIL:
            logger.info(f"Attempting to send email to admin: {ADMIN_EMAIL}")
            email_sent = send_chart_email_via_sendgrid(
                pdf_bytes, 
                ADMIN_EMAIL, 
                f"New Chart Generated: {chart_name}",
                chart_name
            )
            if email_sent:
                logger.info(f"Email successfully sent to admin: {ADMIN_EMAIL}")
            else:
                logger.warning(f"Failed to send email to admin: {ADMIN_EMAIL}")
        else:
            logger.info("No admin email configured, skipping admin email.")
        
        logger.info(f"Email background task completed for {chart_name}.")
    except Exception as e:
        logger.error(f"Error in email background task: {e}", exc_info=True)


# --- API Endpoints ---

@app.post("/calculate_chart")
@limiter.limit("50/day")
async def calculate_chart_endpoint(request: Request, data: ChartRequest):
    try:
        log_data = data.dict()
        if 'full_name' in log_data:
            log_data['chart_name'] = log_data.pop('full_name')
        logger.info("New chart request received", extra=log_data)

        # Ensure ephemeris files are accessible
        ephe_path = os.getenv("SWEP_PATH") or DEFAULT_SWISS_EPHEMERIS_PATH
        if not os.path.exists(ephe_path):
            logger.warning(f"Ephemeris path '{ephe_path}' not found. Falling back to application root.")
            ephe_path = BASE_DIR
        swe.set_ephe_path(ephe_path) 

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
            hour=utc_time.hour, minute=utc_time.minute, latitude=lat, longitude=lng
        )
        chart.calculate_chart(unknown_time=data.unknown_time)
        
        numerology_raw = calculate_numerology(data.day, data.month, data.year)
        # Convert to expected format: {"life_path": ...} -> {"life_path_number": ...}
        numerology = {
            "life_path_number": numerology_raw.get("life_path", "N/A"),
            "day_number": numerology_raw.get("day_number", "N/A"),
            "lucky_number": numerology_raw.get("lucky_number", "N/A")
        }
        
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
        
        # Add quick highlights to the response
        try:
            quick_highlights = get_quick_highlights(full_response, data.unknown_time)
            full_response["quick_highlights"] = quick_highlights
        except Exception as e:
            logger.warning(f"Could not generate quick highlights: {e}")
            full_response["quick_highlights"] = "Quick highlights are unavailable for this chart."
            
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
# Removed rate limit - user wants comprehensive readings without restrictions
async def generate_reading_endpoint(request: Request, reading_data: ReadingRequest, background_tasks: BackgroundTasks):
    """
    This endpoint queues the reading generation and email sending in the background.
    Returns immediately so users can close the browser and still receive their reading via email.
    """
    try:
        user_inputs = reading_data.user_inputs
        chart_name = user_inputs.get('full_name', 'N/A')
        user_email = user_inputs.get('user_email', '')
        
        logger.info(f"Queueing AI reading generation for: {chart_name}")
        
        # Validate that user email is provided (required for background processing)
        if not user_email or not user_email.strip():
            raise HTTPException(
                status_code=400, 
                detail="Email address is required. Your reading will be sent to your email when complete."
            )
        
        # Generate chart hash for polling
        chart_hash = generate_chart_hash(reading_data.chart_data, reading_data.unknown_time)
        
        # Add reading generation and email sending to background task
        # This allows users to close the browser immediately
        background_tasks.add_task(
            generate_reading_and_send_email,
            chart_data=reading_data.chart_data,
            unknown_time=reading_data.unknown_time,
            user_inputs=user_inputs
        )
        logger.info("Background task queued successfully. User can close browser now.")

        # Return immediately - user can close browser
        return {
            "status": "processing",
            "message": "Your comprehensive astrology reading is being generated. This thorough analysis takes up to 15 minutes to complete.",
            "instructions": "You can safely close this page - your reading will be sent to your email when ready. If you choose to wait, the reading will also populate on this page when complete.",
            "email": user_email,
            "estimated_time": "up to 15 minutes",
            "chart_hash": chart_hash  # Include hash for polling
        }
    
    except HTTPException:
        raise
    except Exception as e: 
        logger.error(f"Error queueing reading generation: {e}", exc_info=True)
        # Raise HTTPException to send error detail back to frontend
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_reading/{chart_hash}")
@limiter.limit("100/hour")
async def get_reading_endpoint(request: Request, chart_hash: str):
    """
    Retrieve a completed reading from the cache by chart hash.
    Used by frontend to poll for completed readings.
    """
    # Clean up expired cache entries
    now = datetime.now()
    expired_keys = [
        key for key, value in reading_cache.items()
        if now - value['timestamp'] > timedelta(hours=CACHE_EXPIRY_HOURS)
    ]
    for key in expired_keys:
        del reading_cache[key]
        logger.info(f"Removed expired reading from cache: {key}")
    
    # Check if reading exists in cache
    if chart_hash in reading_cache:
        cached_data = reading_cache[chart_hash]
        return {
            "status": "completed",
            "reading": cached_data['reading'],
            "chart_name": cached_data.get('chart_name', 'N/A')
        }
    else:
        return {
            "status": "processing",
            "message": "Reading is still being generated. Please check again in a moment."
        }
