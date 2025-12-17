from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
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
# Try to import the correct genai package
try:
    import google.generativeai as genai
    GEMINI_PACKAGE_TYPE = "generativeai"
except ImportError:
    try:
        import google.genai as genai
        GEMINI_PACKAGE_TYPE = "genai"
    except ImportError:
        genai = None
        GEMINI_PACKAGE_TYPE = None
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
import re

from llm_schemas import (
    ChartOverviewOutput, CoreTheme, serialize_chart_for_llm,
    format_serialized_chart_for_prompt, parse_json_response,
    GlobalReadingBlueprint, LifeAxis, CoreThemeBullet, SNAPSHOT_PROMPT
)

# --- Import Auth & Database ---
from database import init_db, get_db, User, SavedChart, ChatConversation, ChatMessage, CreditTransaction, AdminBypassLog, FamousPerson
from auth import (
    UserCreate, UserLogin, UserResponse, Token,
    create_user, authenticate_user, get_user_by_email,
    create_access_token, get_current_user, get_current_user_optional
)
from subscription import has_active_subscription, check_subscription_access
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

# --- Import Chat API Router ---
from chat_api import router as chat_router

# --- Import Famous People Router ---
from routers.famous_people_routes import router as famous_people_router

# --- Import Similarity Service ---
from services.similarity_service import find_similar_famous_people_internal

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
GEMINI3_MODEL = os.getenv("GEMINI3_MODEL", "gemini-3-pro-preview")
if GEMINI_API_KEY and genai:
    try:
        if GEMINI_PACKAGE_TYPE == "generativeai":
            # Old google-generativeai package
            genai.configure(api_key=GEMINI_API_KEY)
            logger.info("Configured google-generativeai package")
        elif GEMINI_PACKAGE_TYPE == "genai":
            # New google.genai package - no configure needed, uses Client
            logger.info("Using google.genai package (Client API)")
        else:
            logger.warning("Unknown genai package type")
    except Exception as e:
        logger.error(f"Failed to configure Gemini client: {e}")
elif not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not configured - Gemini 3 readings unavailable unless AI_MODE=stub")
elif not genai:
    logger.error("Could not import google.genai or google.generativeai - Gemini unavailable")

# --- SETUP SENDGRID ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")  # Verified sender email in SendGrid
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")  # Admin email for receiving copies

# --- Swiss Ephemeris configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SWISS_EPHEMERIS_PATH = os.path.join(BASE_DIR, "swiss_ephemeris")

# --- Admin Secret Key for bypassing rate limit ---
ADMIN_SECRET_KEY = os.getenv("FRIENDS_AND_FAMILY_KEY")

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
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            # Check headers (case-insensitive)
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key and friends_and_family_key == ADMIN_SECRET_KEY:
            return str(uuid.uuid4())
    return get_remote_address(request)


# --- SETUP FASTAPI APP & RATE LIMITER ---
limiter = Limiter(key_func=get_rate_limit_key)
app = FastAPI(title="True Sidereal API", version="1.0")
app.state.limiter = limiter

# --- Include Chat API Router ---
app.include_router(chat_router)

# --- Include Famous People Router ---
app.include_router(famous_people_router)

# --- Initialize Database ---
init_db()
logger.info("Database initialized successfully")

# --- Startup Event: Trigger Webpage Deployment ---
@app.on_event("startup")
async def trigger_webpage_deployment():
    """Trigger webpage deployment when API service starts (after new deployment)."""
    WEBPAGE_DEPLOY_HOOK_URL = os.getenv("WEBPAGE_DEPLOY_HOOK_URL")
    
    if not WEBPAGE_DEPLOY_HOOK_URL:
        logger.info("WEBPAGE_DEPLOY_HOOK_URL not configured. Skipping webpage deployment trigger.")
        return
    
    # Trigger in background to not block startup
    try:
        logger.info("Triggering webpage deployment via deploy hook...")
        response = requests.post(
            WEBPAGE_DEPLOY_HOOK_URL,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            logger.info(f"Successfully triggered webpage deployment. Status: {response.status_code}")
        else:
            logger.warning(f"Webpage deployment trigger returned status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        # Don't fail startup if webpage deployment trigger fails
        logger.warning(f"Failed to trigger webpage deployment on startup: {e}")

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

# --- Response Header Middleware ---
from middleware.headers import (
    NormalizeJsonContentTypeMiddleware,
    SecurityHeadersMiddleware,
    ApiNoCacheMiddleware
)

# Add middleware in reverse execution order (last added = first executed on response)
# Execution order on response (reverse of addition):
# 1. ApiNoCacheMiddleware (added last, executes first - can override cache headers)
# 2. SecurityHeadersMiddleware (added second, executes second - sets security defaults)
# 3. NormalizeJsonContentTypeMiddleware (added first, executes last - normalizes content-type)
app.add_middleware(NormalizeJsonContentTypeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ApiNoCacheMiddleware)

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
    is_full_birth_name: bool = False  # If checked, calculate name numerology

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
        self.model_name = GEMINI3_MODEL or "gemini-3-pro-preview"
        self.default_max_tokens = int(os.getenv("GEMINI3_MAX_OUTPUT_TOKENS", "81920"))
        self.client = None
        self.model = None
        if GEMINI_API_KEY and AI_MODE != "stub" and genai:
            try:
                if GEMINI_PACKAGE_TYPE == "generativeai":
                    # Old google-generativeai package
                    self.model = genai.GenerativeModel(self.model_name)
                elif GEMINI_PACKAGE_TYPE == "genai":
                    # New google.genai package uses Client API
                    try:
                        from google.genai import Client
                        self.client = Client(api_key=GEMINI_API_KEY)
                        # Model will be accessed via client.models.generate_content
                    except ImportError:
                        logger.error("Could not import Client from google.genai")
                        self.client = None
                else:
                    logger.warning("Unknown genai package type, cannot initialize model")
            except Exception as e:
                logger.error(f"Error initializing Gemini model '{self.model_name}': {e}")
                self.model = None
                self.client = None
    
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
        
        if self.model is None and (GEMINI_PACKAGE_TYPE == "generativeai" or self.client is None):
            try:
                if GEMINI_PACKAGE_TYPE == "generativeai":
                    # Old API
                    self.model = genai.GenerativeModel(self.model_name)
                elif GEMINI_PACKAGE_TYPE == "genai":
                    # New Client API - initialize client if needed
                    if self.client is None:
                        from google.genai import Client
                        self.client = Client(api_key=GEMINI_API_KEY)
                        logger.info(f"[{call_label}] Initialized google.genai Client")
            except Exception as e:
                logger.error(f"[{call_label}] Failed to initialize Gemini client: {e}", exc_info=True)
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
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": max_tokens,
            }
            
            # Use appropriate API based on which package is available
            if GEMINI_PACKAGE_TYPE == "genai" and self.client is not None:
                # New google.genai Client API - use client.models.generate_content()
                try:
                    logger.info(f"[{call_label}] Attempting client.models.generate_content() with config")
                    response = await self.client.models.generate_content(
                        model=self.model_name,
                        contents=combined_prompt,
                        config={
                            "temperature": generation_config["temperature"],
                            "top_p": generation_config["top_p"],
                            "top_k": generation_config["top_k"],
                            "max_output_tokens": generation_config["max_output_tokens"]
                        }
                    )
                except (TypeError, AttributeError, ValueError) as e:
                    logger.warning(f"[{call_label}] First attempt failed: {e}, trying with individual parameters")
                    # Fallback: try with individual parameters
                    try:
                        response = await self.client.models.generate_content(
                            model=self.model_name,
                            contents=combined_prompt,
                            temperature=generation_config["temperature"],
                            top_p=generation_config["top_p"],
                            top_k=generation_config["top_k"],
                            max_output_tokens=generation_config["max_output_tokens"]
                        )
                    except Exception as e2:
                        logger.warning(f"[{call_label}] Second attempt failed: {e2}, trying simple call")
                        # Last resort: try simple call
                        response = await self.client.models.generate_content(
                            model=self.model_name,
                            contents=combined_prompt
                        )
            elif GEMINI_PACKAGE_TYPE == "generativeai" and self.model is not None:
                # Old google-generativeai API
                response = await self.model.generate_content_async(
                    combined_prompt,
                    generation_config=generation_config
                )
            else:
                raise Exception(f"Cannot generate content - not properly initialized (package_type={GEMINI_PACKAGE_TYPE}, model={self.model is not None}, client={self.client is not None})")
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
    """Gemini Call 0 - produce JSON planning blueprint with forensic depth."""
    import time
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 0: GLOBAL BLUEPRINT GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G0_global_blueprint - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    system_prompt = """You are a master astrological analyst performing FORENSIC CHART SYNTHESIS. Your job is to find the hidden architecture of this person's psyche by weighing every signal.

WEIGHTING HIERARCHY (use this to resolve conflicts):
1. ASPECTS with orb < 3° = strongest signal (especially to Sun, Moon, Ascendant)
2. SIDEREAL placements = soul-level truth, karmic patterns, what they ARE at depth
3. TROPICAL placements = personality expression, how they APPEAR and BEHAVE
4. NUMEROLOGY Life Path = meta-pattern that either confirms or creates tension with astrology
5. CHINESE ZODIAC = elemental overlay that amplifies or softens other signals
6. HOUSE placements = WHERE patterns manifest (career, relationships, etc.)

When sidereal and tropical CONTRADICT:
- The person experiences an internal split (e.g., sidereal Scorpio depth vs tropical Sagittarius optimism)
- This IS the story—don't smooth it over, make it the central tension

When sidereal and tropical ALIGN:
- The signal is amplified—this is a core, undeniable trait
- Cite this as "double confirmation"

Output ONLY JSON. No markdown or commentary outside the JSON object.
Schema (all keys required):
- life_thesis: string paragraph (the ONE sentence that captures their entire journey)
- central_paradox: string (the core contradiction that defines them—be specific)
- core_axes: list of 3-4 objects {name, description, chart_factors[], immature_expression, mature_expression, weighting_rationale}
- top_themes: list of 5 {label, text, evidence_chain} where evidence_chain shows the derivation
- sun_moon_ascendant_plan: list of {body, sidereal_expression, tropical_expression, integration_notes, conflict_or_harmony}
- planetary_clusters: list of {name, members[], description, implications, weight}
- houses_by_domain: list of {domain, summary, indicators[], ruling_planet_state}
- aspect_highlights: list of {title, aspect, orb, meaning, life_applications[], priority_rank}
- patterns: list of {name, description, involved_points[], psychological_function}
- themed_chapters: list of {chapter, thesis, subtopics[], supporting_factors[], key_contradiction}
- shadow_contradictions: list of {tension, drivers[], integration_strategy, what_they_avoid_seeing}
- growth_edges: list of {focus, description, practices[], resistance_prediction}
- final_principles_and_prompts: {principles[], prompts[]}
- snapshot: planning notes for the 7 most disarming psychological truths (specific behaviors, not traits)
- evidence_summary: brief list of the 5 strongest signals in the chart by weight

All notes must cite specific chart factors with their weights."""
    
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "Birth time is UNKNOWN. Avoid relying on houses/angles; focus on sign-level, planetary, and aspect evidence." if unknown_time else "Birth time is known. Houses and angles are available."
    user_prompt = f"""Chart Summary:
{chart_summary}

Serialized Chart Data:
{serialized_chart_json}

Context:
- {time_note}
- You are performing FORENSIC ANALYSIS. Find the hidden architecture.
- For every claim, trace the evidence chain: which placements + aspects + numerology converge to create it?
- Identify the CENTRAL PARADOX: the one contradiction that explains most of their struggles and gifts.
- Weight signals using the hierarchy: tight aspects > sidereal > tropical > numerology > Chinese zodiac > houses.
- The snapshot field should capture 7 specific BEHAVIORS (not traits) that would make someone say "how do they know that?"
- The evidence_summary should list the 5 heaviest signals in priority order.

Return ONLY the JSON object."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=12000,
        temperature=0.2,
        call_label="G0_global_blueprint"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G0_global_blueprint completed in {step_duration:.2f} seconds")
    logger.info(f"G0 API calls made: {step_calls}")
    logger.info(f"G0 step cost: ${step_cost:.6f} USD")
    logger.info(f"G0 response length: {len(response_text)} characters")
    
    blueprint_parsed = parse_json_response(response_text, GlobalReadingBlueprint)
    if blueprint_parsed:
        logger.info("G0 parsed blueprint successfully")
        logger.info("="*80)
        return {"parsed": blueprint_parsed, "raw_text": response_text}
    
    logger.warning("G0 blueprint parsing failed - returning raw JSON text fallback")
    logger.info("="*80)
    return {"parsed": None, "raw_text": response_text}


async def g1_natal_foundation(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    unknown_time: bool
) -> str:
    """Gemini Call 1 - Natal foundations + personal/social planets."""
    import time
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 1: NATAL FOUNDATION GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G1_natal_foundation - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Blueprint parsed: {blueprint.get('parsed') is not None}")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    time_note = "After the Snapshot, include a short 'What We Know / What We Don't Know' paragraph clarifying birth time is unknown. Avoid houses/angles entirely." if unknown_time else "You may cite houses and angles explicitly."
    
    system_prompt = """You are The Synthesizer performing FORENSIC PSYCHOLOGICAL RECONSTRUCTION.

Your reader should finish this reading feeling like their psyche has been X-rayed. Every paragraph must show WHY you know what you know—not by explaining astrology, but by making the evidence visible through specificity.

EVIDENCE DENSITY RULE: Every paragraph must contain:
1. A specific claim about behavior/psychology
2. The phrase "because" or "this comes from" followed by 2-3 chart factors
3. A concrete example showing how it manifests

WEIGHTING (use this to resolve contradictions):
- Tight aspects (< 3° orb) override sign placements
- Sidereal = what they ARE at soul level (karmic, deep, persistent)
- Tropical = how they APPEAR and ACT (personality, behavior, first impression)
- When sidereal/tropical contradict: THIS IS THE STORY—the internal split IS the insight
- Numerology Life Path = meta-pattern confirming or challenging astrology
- Chinese Zodiac = elemental amplifier/softener

CUMULATIVE REVELATION STRUCTURE:
- Snapshot = "I see you" (specific behaviors that feel uncanny)
- Overview = "Here's why" (the architecture behind the behaviors)
- Houses = "Here's where it plays out" (life domains)

Tone: Forensic psychologist briefing a client. Clinical precision, warm delivery, zero fluff.

Scope for this call:
- Snapshot (7 bullets, no lead-in)
- Chart Overview & Core Themes
- Houses & Life Domains summary

Rules:
- Start immediately with SNAPSHOT heading. No preamble.
- NO markdown, bold/italic, emojis, or decorative separators.
- Every claim must have visible evidence (chart factors named).
- Make the reader feel the WEIGHT of the analysis through specificity, not explanation."""
    
    heading_block = "   WHAT WE KNOW / WHAT WE DON'T KNOW\n" if unknown_time else ""
    
    if unknown_time:
        houses_instruction = "SKIP THIS SECTION ENTIRELY. Since birth time is unknown, we cannot calculate houses. Do NOT write anything about houses or life domains. Do NOT mention that birth time is unknown here—that was already covered in the What We Know section. Simply omit this section completely."
    else:
        houses_instruction = """CRITICAL: You MUST cover ALL 12 houses. Do not skip any house. Each house gets its own detailed subsection.

Cover each house in this exact order with the heading format: [NUMBER]st/nd/rd/th HOUSE: [NAME]

1st HOUSE: SELF & IDENTITY
2nd HOUSE: RESOURCES & VALUES
3rd HOUSE: COMMUNICATION & LEARNING
4th HOUSE: HOME & ROOTS
5th HOUSE: CREATIVITY & PLEASURE
6th HOUSE: WORK & HEALTH
7th HOUSE: RELATIONSHIPS & PARTNERSHIPS
8th HOUSE: TRANSFORMATION & SHARED RESOURCES
9th HOUSE: PHILOSOPHY & HIGHER LEARNING
10th HOUSE: CAREER & PUBLIC STANDING
11th HOUSE: FRIENDS & ASPIRATIONS
12th HOUSE: SPIRITUALITY & UNCONSCIOUS

For EACH of the 12 houses, you MUST provide a COMPREHENSIVE, DETAILED analysis following this structure:

1. HOUSE CUSP & RULER (2-3 paragraphs):
   - The sign on the cusp in BOTH sidereal and tropical systems (note if they differ and what that means)
   - The ruling planet(s) for that sign
   - Where the ruling planet is located (sign, house, degree) in BOTH sidereal and tropical systems
   - The condition of the ruler (dignified, debilitated, retrograde, in fall, in detriment, etc.) in both systems
   - What the ruler's condition tells us about how this life domain functions
   - How the ruler's placement in another house connects this domain to that other area of life

2. ALL PLANETS IN THE HOUSE (3-5 paragraphs):
   - List EVERY planet that falls in this house in the SIDEREAL system (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Nodes, etc.)
   - List EVERY planet that falls in this house in the TROPICAL system
   - For EACH planet, provide detailed analysis:
     * Its sign placement (in both systems if different)
     * Its exact degree
     * Its house position
     * Its aspects (list all major aspects to other planets)
     * Whether it's retrograde
     * What this planet's presence in this house means for this life domain
   - Compare sidereal vs tropical placements - note where planets appear in different houses between systems and what that contradiction means
   - If a planet appears in this house in one system but not the other, explain the significance

3. ALL ZODIAC SIGNS IN THE HOUSE (2-3 paragraphs):
   - Identify ALL signs that appear within this house (houses can span multiple signs)
   - Note the exact degree ranges for each sign within the house
   - Explain how each sign's energy influences this life domain
   - Compare sidereal vs tropical sign distributions in the house
   - Show how different signs within the house create layers or phases in this domain

4. SYNTHESIS & INTEGRATION (4-6 paragraphs):
   - Show how the domain is "engineered" by multiple factors converging (house ruler + ALL planets in house + sign distributions + aspects to cusp)
   - Explain how sidereal placements reveal the SOUL-LEVEL approach to this domain
   - Explain how tropical placements reveal the PERSONALITY-LEVEL approach to this domain
   - Note any contradictions or tensions between sidereal and tropical placements and what that means
   - Give MULTIPLE concrete examples of how this shows up in real life (at least 3-4 specific scenarios)
   - Connect to numerology where relevant (Life Path, Day Number, etc.)
   - Connect to Chinese zodiac if relevant
   - If the house is empty (no planets), explain what that means - but still provide substantial analysis of the ruler and sign distributions
   - Show how this house connects to other houses through planetary rulerships

5. STELLIUMS & CONCENTRATIONS (if applicable, 2-3 paragraphs):
   - If 3+ planets are in this house, analyze the stellium energy in detail
   - Explain how it concentrates focus in this domain
   - Note if the stellium appears in sidereal, tropical, or both systems
   - Show how the stellium creates intensity, focus, or complexity in this area

6. REAL-LIFE EXPRESSION (2-3 paragraphs):
   - Provide concrete, specific examples of how this house manifests in daily life
   - Give scenarios, behaviors, or life patterns that show this house's energy
   - Connect to the overall chart themes from earlier sections

CRITICAL REQUIREMENTS:
- You MUST cover ALL 12 houses - do not skip any
- Each house should be substantial (at least 10-15 paragraphs total per house)
- Be thorough - examine every planet, every sign, and both systems
- Use specific degree references and aspect details
- Provide concrete examples, not generic descriptions
- Show the forensic analysis - make the reader feel the weight of the analysis"""
    
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
   SNAPSHOT: WHAT WILL FEEL MOST TRUE ABOUT YOU
   SYNTHESIS ASTROLOGY'S THESIS ON YOUR CHART (no colon in heading)
{heading_block}   CHART OVERVIEW & CORE THEMES
   HOUSES & LIFE DOMAINS SUMMARY

2. SNAPSHOT: THIS SECTION MUST BE A BULLETED LIST. FORMAT IS CRITICAL.
   
   OUTPUT FORMAT (follow exactly):
   - [First bullet point sentence here]
   - [Second bullet point sentence here]
   - [Third bullet point sentence here]
   - [Fourth bullet point sentence here]
   - [Fifth bullet point sentence here]
   - [Sixth bullet point sentence here]
   - [Seventh bullet point sentence here]
   
   RULES:
   - Exactly 7 bullets, each starting with "- " (dash space)
   - Each bullet is 1-2 sentences about a SPECIFIC BEHAVIOR or PATTERN
   - NO intro paragraph before the bullets
   - NO outro paragraph after the bullets
   - NO astrological jargon (no planets, signs, houses, aspects)
   - Every bullet should make the reader think "how do they know that?!"
   
{SNAPSHOT_PROMPT.strip()}

Blueprint notes for Snapshot (use them to prioritize chart factors):
{snapshot_notes}

3. SYNTHESIS ASTROLOGY'S THESIS ON YOUR CHART (write this heading exactly as shown, no colon after SYNTHESIS): Immediately after the Snapshot bullets, write a single powerful paragraph (4-6 sentences) that captures the CENTRAL THESIS of this person's chart. This is the "life_thesis" from the blueprint—the one core truth that everything else orbits around.
   
   FORMAT:
   - One paragraph, no bullets
   - Start with a bold, direct statement about who this person IS at their core
   - Reference the central_paradox from the blueprint
   - Name the primary tension they navigate daily
   - End with what integration/growth looks like for them
   - Use "you" language, be direct and confident
   - NO astrological jargon in this section—speak in psychological/behavioral terms
   
   This should feel like the "thesis statement" of their entire reading—if someone only read this paragraph, they'd understand the essence of the chart.

4. Chart Overview & Core Themes: This is the HEART of the reading. Structure each of the 5 themes as:
   
   THEME TITLE (plain language, no jargon)
   
   Opening: 2-3 sentences stating the pattern in everyday language. Make this vivid and specific.
   
   The Evidence (3-4 sentences): "This shows up because [Sidereal X] creates [quality], while [Tropical Y] adds [quality], and this tension is [amplified/softened] by [Aspect Z at N° orb]. Your Life Path [N] [confirms/complicates] this by [specific connection]. Additionally, [another chart factor] reinforces this pattern by [explanation]."
   
   How It Plays Out (3-4 sentences): Describe multiple specific scenarios—a relationship moment, a work situation, AND an internal experience. Be concrete: "When your partner criticizes you, you..." or "In meetings, you tend to..."
   
   The Contradiction (2-3 sentences): If sidereal and tropical pull in different directions, name the internal split explicitly: "Part of you [sidereal quality], while another part [tropical quality]. This creates an ongoing negotiation where [specific behavior]. You've probably noticed this most when [situation]."
   
   Integration Hint (1-2 sentences): What does growth look like for this specific theme?
   
   CRITICAL: Use blueprint.sun_moon_ascendant_plan extensively. At least 2 of the 5 themes MUST be anchored in Sun, Moon, or Ascendant dynamics. For each, reference:
   - The sidereal_expression and tropical_expression from the plan
   - The conflict_or_harmony field to determine if this is a tension or amplification
   - The integration_notes to inform the growth direction
   
   End with a SUBSTANTIAL SYNTHESIS PARAGRAPH (5-7 sentences) that:
   - Names the central paradox from the blueprint
   - Shows how the 5 themes interact and reinforce each other
   - Identifies the ONE thing that would shift everything if they worked on it
   - Describes what integration looks like in concrete daily terms
   - Ends with an empowering but realistic statement about their potential

5. Houses & Life Domains: {houses_instruction}

6. EVIDENCE TRAIL: Every paragraph must make the reader feel the weight of analysis by naming specific factors. Use phrases like:
   - "because your [placement] at [degree] [aspect] your [other placement]"
   - "this is amplified by"
   - "the [numerology number] confirms this pattern"
   - "your [Chinese zodiac element] adds [quality] to this dynamic"

7. No markdown, decorative characters, or horizontal rules.

8. Keep Action Checklist for later sections."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.7,
        call_label="G1_natal_foundation"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G1_natal_foundation completed in {step_duration:.2f} seconds")
    logger.info(f"G1 API calls made: {step_calls}")
    logger.info(f"G1 step cost: ${step_cost:.6f} USD")
    logger.info(f"G1 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text


async def g2_deep_dive_chapters(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    blueprint: Dict[str, Any],
    natal_sections: str,
    unknown_time: bool
) -> str:
    """Gemini Call 2 - Themed chapters, aspects, shadow, owner's manual."""
    import time
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 2: DEEP DIVE CHAPTERS GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G2_deep_dive_chapters - Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Natal sections length: {len(natal_sections)} characters")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    blueprint_json = _blueprint_to_json(blueprint)
    serialized_chart_json = json.dumps(serialized_chart, indent=2)
    
    system_prompt = """You are continuing the FORENSIC PSYCHOLOGICAL RECONSTRUCTION.

The earlier sections established the architecture. Now you're showing how it PLAYS OUT in specific life domains. Each section should feel like a case study with evidence.

CUMULATIVE REVELATION: Each section should DEEPEN what came before, not just add to it. Reference earlier themes explicitly: "The [Theme X] pattern from your overview manifests here as..."

EVIDENCE DENSITY: Every paragraph needs:
1. A specific claim about this life domain
2. The chart factors that create it (sidereal + tropical + aspects + numerology)
3. A concrete scenario or behavior

WEIGHTING REMINDER:
- Tight aspects (< 3°) are the loudest signals
- Sidereal = soul-level truth, tropical = personality expression
- When they contradict, the SPLIT is the insight
- Numerology confirms or complicates
- Chinese zodiac amplifies or softens

Scope for this call:
- LOVE, RELATIONSHIPS & ATTACHMENT
- WORK, MONEY & VOCATION
- EMOTIONAL LIFE, FAMILY & HEALING
- SPIRITUAL PATH & MEANING
- MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS
- SHADOW, CONTRADICTIONS & GROWTH EDGES
- OWNER'S MANUAL: FINAL INTEGRATION (with Action Checklist)

NO APPENDIX. Planetary details should be woven into the themed chapters where they matter most.

Guardrails:
- Read earlier sections and BUILD on them—don't repeat, deepen.
- Use blueprint data for each section.
- Every paragraph must have visible evidence (chart factors named).
- Each themed chapter must name the KEY CONTRADICTION for that life area.
- Maintain forensic precision with warm delivery.
- No markdown, decorative characters, or separators."""
    
    user_prompt = f"""[CHART SUMMARY]\n{chart_summary}\n
[SERIALIZED CHART DATA]\n{serialized_chart_json}\n
[BLUEPRINT JSON]\n{blueprint_json}\n
[PRIOR SECTIONS ALREADY WRITTEN]\n{natal_sections}\n
BLUEPRINT DATA TO USE:
- blueprint.sun_moon_ascendant_plan: Reference the sidereal/tropical expressions and integration_notes for Sun, Moon, Ascendant throughout these sections
- blueprint.themed_chapters: Use the thesis, subtopics, and key_contradiction for each chapter
- blueprint.aspect_highlights: For the Aspects section
- blueprint.patterns: For pattern summaries
- blueprint.shadow_contradictions and growth_edges: For Shadow section
- blueprint.final_principles_and_prompts: For Owner's Manual

Section instructions:
LOVE, RELATIONSHIPS & ATTACHMENT
- Use Venus, Mars, Nodes, Juno, 5th/7th houses (if time known) plus relevant aspects/patterns.
- Reference blueprint.sun_moon_ascendant_plan.Moon data—the Moon's sidereal/tropical split directly shapes emotional needs in relationships.
- Provide at least 3 concrete relational dynamics that show contradiction + lesson. Every paragraph must cite multiple signals (e.g., Venus/Mars aspect + nodal axis + numerology) and end with "so this often looks like…".

WORK, MONEY & VOCATION
- Integrate Midheaven/10th/2nd houses when available, Saturn/Jupiter signatures, dominant elements, numerology if reinforcing.
- Reference blueprint.sun_moon_ascendant_plan.Sun data—the Sun's sidereal/tropical split shapes core identity and career expression.
- Show how internal motives (from earlier sections) become strategy, and call back to Mars/Saturn themes where relevant.

EMOTIONAL LIFE, FAMILY & HEALING
- Use Moon aspects, 4th/8th/12th houses, Chiron, blueprint notes.
- Reference blueprint.sun_moon_ascendant_plan.Moon extensively—this is the Moon's primary domain.
- Reveal family imprints and healing arcs with visceral examples (e.g., "This is the moment you shut down during conflict…").

SPIRITUAL PATH & MEANING
- Nodes, Neptune, Pluto, numerology, blueprint spiritual chapter. Explain how surrender vs control repeats everywhere, and prescribe tangible practices that tie back to numerology/Life Path.

MAJOR LIFE DYNAMICS: THE TIGHTEST ASPECTS & PATTERNS

This section covers the TOP 5 TIGHTEST ASPECTS (by orb) plus any significant aspect patterns in the chart.

FORMAT FOR EACH ASPECT (cover ONLY the TOP 5 tightest aspects, ordered by orb from tightest to widest):

[PLANET 1] [ASPECT TYPE] [PLANET 2] ([orb]°)

[Paragraph 1: Core Dynamic - Name the fundamental tension or gift this creates. Explain the archetypal meaning of this aspect combination. What is the essential dynamic between these two planetary energies?]

[Paragraph 2: Why This Matters - Explain the psychological mechanism. What does this aspect create internally? How does it shape their default responses, emotional patterns, and decision-making? Reference both sidereal and tropical contexts if relevant. Show how this aspect amplifies or modifies the individual planet meanings. Provide concrete examples of how this shows up in relationships, work, or daily life.]

[Paragraph 3: The Growth Edge - What shifts when they work with this consciously? What's the integrated expression vs the reactive pattern? What does mastery of this aspect look like?]

---

[Leave a blank line and "---" separator between each aspect for readability]

AFTER THE 5 ASPECTS, ADD A SECTION ON ASPECT PATTERNS:

ASPECT PATTERNS IN YOUR CHART

For each significant pattern found in the chart (Grand Trines, T-Squares, Stelliums, Yods, Kites, Grand Crosses, Mystic Rectangles, etc.):

[PATTERN NAME]: [Planets involved - list all planets with their signs and houses]

[Paragraph 1: What This Geometry Creates - Explain the psychological function. How does this shape concentrate or distribute energy? What is the archetypal meaning of this pattern? How do the planets interact within this geometry? What are the strengths and challenges?]

[Paragraph 2: The Life Theme - Connect to earlier themes in the reading. How does this pattern reinforce or complicate themes from the Chart Overview? What life areas does this pattern most strongly influence? Provide concrete examples of how this pattern shows up in their daily life or major life decisions.]

[Paragraph 3: The Integration Path - How to work with this pattern consciously. What awareness or practices help them navigate this pattern? What does integration look like?]

---

[Use "---" between each pattern for visual separation]

CRITICAL REQUIREMENTS:
- Cover ONLY the TOP 5 tightest aspects (prioritize by orb - tightest first)
- Each aspect should be EXACTLY 3 paragraphs (not more, not less)
- Be detailed and specific - show the forensic analysis
- Provide concrete examples, not generic descriptions
- Reference both sidereal and tropical placements where relevant
- Connect aspects to the overall chart themes
- Include ALL significant aspect patterns found in the chart
- Each pattern should be EXACTLY 3 paragraphs

SHADOW, CONTRADICTIONS & GROWTH EDGES

This section should be COMPREHENSIVE and DEEP. Format with clear subsections and substantial content.

For each shadow pattern, use this detailed structure:

SHADOW: [Name of the Shadow Pattern]

The Pattern: [3-4 paragraphs describing what this looks like in behavior. Be specific and detailed. Give concrete examples of how this shadow pattern manifests. What are the observable behaviors, reactions, or patterns? How does this show up in relationships, work, or internal experience?]

The Driver: [4-5 paragraphs explaining WHY this pattern exists - what chart factors create it. Reference specific placements, aspects, and patterns from the chart. Show the forensic analysis - which planets, signs, houses, and aspects create this shadow? Explain the psychological mechanism. How do sidereal and tropical placements contribute? Connect to numerology or other factors if relevant. Show the evidence chain that creates this pattern.]

The Contradiction: [2-3 paragraphs explaining the internal contradiction or tension. What are the competing needs or energies? How does this create internal conflict? What is the person avoiding or not seeing?]

The Cost: [3-4 paragraphs on what this costs them in life/relationships. Be specific - how does this shadow pattern limit them? What opportunities does it close? What relationships does it damage? What growth does it prevent? Give concrete examples.]

The Integration: [4-5 paragraphs with concrete "pattern interrupts" and integration strategies. What can they DO differently? Provide specific practices, awareness exercises, or approaches. What does working with this shadow consciously look like? What is the integrated expression? How can they transform this pattern? Give actionable steps and concrete examples of the shift.]

Real-Life Example: [2-3 paragraphs with a concrete scenario showing this shadow pattern in action, and then showing how the integrated approach would look different.]

---

[Use "---" between each shadow pattern for visual separation]

Cover at least 4-5 shadow patterns from blueprint.shadow_contradictions. Be thorough and comprehensive.

GROWTH EDGES

After the shadow patterns, add a section called "Growth Edges" with actionable experiments and practices:

For each growth edge, provide:

[GROWTH EDGE NAME]

The Opportunity: [2-3 paragraphs explaining what this growth edge represents. What potential does this unlock? What becomes possible when they develop this?]

The Chart Evidence: [2-3 paragraphs showing which chart factors support this growth. Reference specific placements, aspects, or patterns that indicate this potential.]

The Practice: [3-4 paragraphs with specific, actionable experiments or practices. What can they do to develop this? Give concrete exercises, awareness practices, or approaches. Be detailed and specific - not vague suggestions.]

The Integration: [2-3 paragraphs on how this growth edge connects to the overall chart themes and shadow patterns. How does developing this help integrate the shadows?]

---

[Use "---" between each growth edge for visual separation]

Cover at least 4-5 growth edges from blueprint.growth_edges. Make them substantial and actionable.

CRITICAL REQUIREMENTS:
- Each shadow pattern should be substantial (at least 15-20 paragraphs per pattern)
- Each growth edge should be substantial (at least 10-12 paragraphs per edge)
- Be extremely detailed and specific - show the forensic analysis
- Provide concrete examples, practices, and actionable steps
- Reference specific chart factors throughout
- Make the reader feel the depth and weight of the analysis

- [Growth edge 1]: [Concrete experiment they can try, tied to a specific pattern]
- [Growth edge 2]: [Concrete experiment they can try, tied to a specific pattern]
- [Growth edge 3]: [Concrete experiment they can try, tied to a specific pattern]

Each growth edge bullet must start with "- " and be 1-2 sentences.

OWNER'S MANUAL: FINAL INTEGRATION
This is the "so what do I do with all this?" section. Structure it as:

YOUR OPERATING SYSTEM (2-3 paragraphs)
- Synthesize the central paradox and how it affects daily decisions
- Name the "default mode" they fall into under stress (with evidence)
- Name the "high expression" mode they access when integrated

GUIDING PRINCIPLES (3-4 principles)
Each principle must:
- Reference a specific theme or pattern from earlier
- Be actionable, not abstract
- Include the "because" (why this principle matters for THIS chart)

INTEGRATION PROMPTS (3-4 questions)
Questions they should sit with, each tied to a specific chart dynamic.

ACTION CHECKLIST (7 bullets)
Format each bullet EXACTLY like this, starting with "- " on its own line:
- [Action verb] [specific task] this week. This addresses [Theme/Section reference] which showed [specific pattern].

Each bullet must:
- Start on a new line with "- " (dash space)
- Begin with a specific action verb (Practice, Notice, Try, Schedule, Write, Ask, etc.)
- Be concrete enough to do THIS WEEK
- Reference which section/theme it addresses
- Keep each bullet to 1-2 sentences maximum

Example format:
- Practice pausing for 3 breaths before responding to criticism this week. This addresses Theme 2 (The Reactive Protector) which showed your Mars-Moon square creates defensive reactions.
- Notice when you're overexplaining yourself in conversations. This addresses the Mercury-Jupiter opposition from Major Aspects which creates a tendency to over-justify.

Unknown time handling: {'Do NOT cite houses/angles; speak in terms of domains, signs, and aspects.' if unknown_time else 'You may cite houses/angles explicitly.'}

FINAL INSTRUCTION: The reading should end with a single paragraph that returns to the life_thesis from the blueprint—the ONE sentence that captures their entire journey. This creates closure and makes the reader feel the coherence of the entire analysis."""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.7,
        call_label="G2_deep_dive_chapters"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G2_deep_dive_chapters completed in {step_duration:.2f} seconds")
    logger.info(f"G2 API calls made: {step_calls}")
    logger.info(f"G2 step cost: ${step_cost:.6f} USD")
    logger.info(f"G2 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text


async def g3_polish_full_reading(
    llm: Gemini3Client,
    full_draft: str,
    chart_summary: str
) -> str:
    """Gemini Call 3 - polish entire reading for forensic coherence."""
    import time
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 3: POLISH FULL READING")
    logger.info("="*80)
    logger.info(f"Starting G3_polish_full_reading - Full draft length: {len(full_draft)} characters")
    logger.info(f"Chart summary length: {len(chart_summary)} chars")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    system_prompt = """You are the final editor ensuring this reading feels like a FORENSIC RECONSTRUCTION—coherent, weighted, and undeniably specific.

COHERENCE CHECK:
1. Does every section BUILD on previous sections? Add explicit callbacks: "As we saw in [Section]..." or "This connects to [Theme X]..."
2. Does the central paradox thread through the entire reading? It should be named in Overview, visible in each themed chapter, and resolved in Owner's Manual.
3. Are late revelations reflected earlier? If Shadow section reveals something important, ensure Overview or Snapshot hints at it.

EVIDENCE DENSITY CHECK:
1. Does every claim have visible evidence (chart factors named)?
2. Are the "because" statements specific? Not "because of your chart" but "because your Moon at 15° Scorpio squares your Sun"
3. Is the weighting clear? When factors contradict, is the resolution explained?

IMPACT CHECK:
1. Does Snapshot feel uncanny? Each bullet should make reader think "how do they know that?"
2. Does each paragraph earn its existence? Cut fluff, tighten sentences, make every word count.
3. Does the reading ESCALATE? The most powerful insight should come in Shadow or Owner's Manual, not early.

TONE CHECK:
1. Clinical precision + warm delivery
2. Second person throughout
3. Confident but non-absolute ("you tend to" not "you always")
4. Zero fluff, zero filler, zero generic statements

Preserve all section headings and bullet counts. You may rewrite any sentence to improve coherence and impact."""
    
    user_prompt = f"""Full draft to polish:
{full_draft}

Reference chart summary (for context only, do not restate):
{chart_summary}

Return the polished reading. Ensure:
1. Central paradox is visible throughout
2. Every section builds on previous ones
3. Evidence is specific and weighted
4. The reading feels like a forensic reconstruction, not a horoscope"""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=81920,
        temperature=0.4,
        call_label="G3_polish_full_reading"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G3_polish_full_reading completed in {step_duration:.2f} seconds")
    logger.info(f"G3 API calls made: {step_calls}")
    logger.info(f"G3 step cost: ${step_cost:.6f} USD")
    logger.info(f"G3 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text


async def g4_famous_people_section(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    famous_people_matches: list,
    unknown_time: bool
) -> str:
    """Gemini Call 4 - Generate famous people comparison section."""
    import time
    step_start_time = time.time()
    logger.info("="*80)
    logger.info("STEP 4: FAMOUS PEOPLE SECTION GENERATION")
    logger.info("="*80)
    logger.info(f"Starting G4_famous_people_section - Number of matches: {len(famous_people_matches)}")
    logger.info(f"Chart summary length: {len(chart_summary)} chars")
    logger.info(f"Unknown time: {unknown_time}")
    
    # Track cost before call
    cost_before = llm.total_cost_usd
    call_count_before = llm.call_count
    
    # Format famous people data for the LLM - limit to top 8
    famous_people_data = []
    for match in famous_people_matches[:8]:  # Limit to top 8
        fp_data = {
            "name": match.get("name", "Unknown"),
            "occupation": match.get("occupation", ""),
            "similarity_score": match.get("similarity_score", 0),
            "matching_factors": match.get("matching_factors", []),
            "birth_date": match.get("birth_date", ""),
            "birth_location": match.get("birth_location", ""),
        }
        famous_people_data.append(fp_data)
    
    famous_people_json = json.dumps(famous_people_data, indent=2)
    
    system_prompt = """You are an expert astrologer analyzing chart similarities between the user and famous historical figures.

Your task is to provide DEEP, DETAILED analysis that:
1. References EACH matching placement explicitly and explains what it means
2. Shows how multiple matching placements create a coherent psychological pattern
3. Connects chart similarities to observable traits, life patterns, and archetypal energies
4. Provides substantial, insightful analysis (not brief summaries)

Be extremely specific and forensic:
- Name EVERY matching placement from the matching_factors list
- Explain what EACH placement means individually
- Show how the COMBINATION of placements creates a unique pattern
- Connect to psychological traits, life themes, strengths, and challenges
- Provide concrete examples of how these patterns manifest
- Be insightful, detailed, and comprehensive

Tone: Clinical precision with warm delivery. Second person ("you share...", "like [famous person], you...")."""
    
    user_prompt = f"""**User's Chart Summary:**
{chart_summary}

**Famous People Matches:**
{famous_people_json}

**Instructions:**
Write a section titled "Famous People & Chart Similarities" that:

1. Introduction (2-3 paragraphs): Explain that sharing chart patterns with notable figures reveals archetypal energies and life themes. Explain how these similarities work and what they mean.

2. For EACH of the top 8 highest scoring matches (process ALL 8, ordered by similarity_score from highest to lowest):

   Format each person as follows:
   
   [PERSON NAME] ([OCCUPATION/NOTABILITY])
   
   Chart Similarities:
   - Go through EACH matching factor from the matching_factors list
   - For EACH matching placement, write 2-3 sentences explaining:
     * What this specific placement means (e.g., "Sun in Aries (Sidereal) indicates...")
     * How this placement shapes personality, behavior, or life patterns
     * What this suggests about core identity, emotional needs, or life themes
   
   Psychological Patterns:
   - Write 3-4 paragraphs analyzing the COMBINATION of matching placements
   - Show how multiple placements create a coherent psychological profile
   - Explain what these shared patterns suggest about:
     * Core psychological traits and motivations
     * Life themes or archetypal energies
     * Potential strengths and how they manifest
     * Potential challenges and how they show up
   - Be specific: "The combination of [Placement 1] and [Placement 2] creates [pattern]. Like [famous person], this manifests as [concrete example from their life or work]. In your life, this might show up as [specific scenario]."
   
   What This Reveals:
   - Write 2-3 paragraphs connecting the chart similarities to observable traits
   - Reference specific examples from the famous person's life or work
   - Explain what these patterns suggest about the user's potential
   - Be detailed and insightful, not generic

3. Synthesis (3-4 paragraphs): After covering all 8 people, write a comprehensive synthesis that:
   - Identifies common themes across multiple matches
   - Explains what these collective similarities reveal about the user's archetypal patterns
   - Shows how different matches highlight different aspects of the user's chart
   - Connects to the overall reading themes
   - Provides insight into potential life themes and directions

**Critical Requirements:**
- Cover ALL 8 top matches (not just 3-5)
- Reference EACH matching placement explicitly from the matching_factors list
- Write SUBSTANTIAL content for each person (at least 5-7 paragraphs per person)
- Don't just list similarities—explain what they MEAN in depth
- Connect chart patterns to psychological/life patterns with concrete examples
- Be insightful, detailed, and comprehensive
- If birth time is unknown, don't mention house placements
- Use second person throughout
- No markdown, bold, or decorative separators"""
    
    response_text = await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=32768,  # Increased for detailed famous people analysis
        temperature=0.7,
        call_label="G4_famous_people_section"
    )
    
    # Calculate step cost and timing
    step_duration = time.time() - step_start_time
    cost_after = llm.total_cost_usd
    step_cost = cost_after - cost_before
    call_count_after = llm.call_count
    step_calls = call_count_after - call_count_before
    
    logger.info(f"G4_famous_people_section completed in {step_duration:.2f} seconds")
    logger.info(f"G4 API calls made: {step_calls}")
    logger.info(f"G4 step cost: ${step_cost:.6f} USD")
    logger.info(f"G4 response length: {len(response_text)} characters")
    logger.info("="*80)
    
    return response_text


def serialize_snapshot_data(chart_data: dict, unknown_time: bool) -> dict:
    """
    Serialize only the snapshot data: 2 tightest aspects, stelliums, Sun/Moon/Rising
    from both sidereal and tropical systems. This is blinded (no name, birthdate, location).
    """
    snapshot = {
        "metadata": {
            "unknown_time": unknown_time
        },
        "core_identity": {
            "sidereal": {},
            "tropical": {}
        },
        "tightest_aspects": {
            "sidereal": [],
            "tropical": []
        },
        "stelliums": {
            "sidereal": [],
            "tropical": []
        }
    }
    
    # Extract Sun, Moon, Rising from sidereal
    s_positions = {p['name']: p for p in chart_data.get('sidereal_major_positions', [])}
    s_extra = {p['name']: p for p in chart_data.get('sidereal_additional_points', [])}
    
    def extract_sign_from_position(position_str):
        """Extract sign name from position string like '25°30' Capricorn'"""
        if not position_str:
            return 'N/A'
        parts = position_str.split()
        return parts[-1] if parts else 'N/A'
    
    for body_name in ['Sun', 'Moon']:
        if body_name in s_positions:
            body = s_positions[body_name]
            position_str = body.get('position', '')
            snapshot["core_identity"]["sidereal"][body_name.lower()] = {
                "sign": extract_sign_from_position(position_str),
                "degree": body.get('degrees', 0),
                "house": body.get('house_num') if not unknown_time else None,
                "retrograde": body.get('retrograde', False)
            }
    
    # Ascendant (if known time)
    if not unknown_time and 'Ascendant' in s_extra:
        asc = s_extra['Ascendant']
        info_str = asc.get('info', '')
        sign = extract_sign_from_position(info_str)
        # Try to extract degree from info string (format: "Sign degree°" or "Sign degree° – House X")
        degree = 0
        if info_str:
            parts = info_str.split()
            for i, part in enumerate(parts):
                if '°' in part:
                    try:
                        degree = float(part.replace('°', '').replace("'", ''))
                        break
                    except (ValueError, AttributeError):
                        pass
        snapshot["core_identity"]["sidereal"]["ascendant"] = {
            "sign": sign,
            "degree": degree
        }
    
    # Extract Sun, Moon, Rising from tropical
    t_positions = {p['name']: p for p in chart_data.get('tropical_major_positions', [])}
    t_extra = {p['name']: p for p in chart_data.get('tropical_additional_points', [])}
    
    for body_name in ['Sun', 'Moon']:
        if body_name in t_positions:
            body = t_positions[body_name]
            position_str = body.get('position', '')
            snapshot["core_identity"]["tropical"][body_name.lower()] = {
                "sign": extract_sign_from_position(position_str),
                "degree": body.get('degrees', 0),
                "house": body.get('house_num') if not unknown_time else None,
                "retrograde": body.get('retrograde', False)
            }
    
    # Ascendant (if known time)
    if not unknown_time and 'Ascendant' in t_extra:
        asc = t_extra['Ascendant']
        info_str = asc.get('info', '')
        sign = extract_sign_from_position(info_str)
        # Try to extract degree from info string (format: "Sign degree°" or "Sign degree° – House X")
        degree = 0
        if info_str:
            parts = info_str.split()
            for i, part in enumerate(parts):
                if '°' in part:
                    try:
                        degree = float(part.replace('°', '').replace("'", ''))
                        break
                    except (ValueError, AttributeError):
                        pass
        snapshot["core_identity"]["tropical"]["ascendant"] = {
            "sign": sign,
            "degree": degree
        }
    
    # Get 2 tightest aspects from sidereal (sorted by score, then orb)
    s_aspects = chart_data.get('sidereal_aspects', [])
    if s_aspects:
        def parse_score(score_val):
            try:
                if isinstance(score_val, str):
                    return float(score_val)
                return float(score_val)
            except (ValueError, TypeError):
                return 0.0
        
        def parse_orb(orb_val):
            try:
                if isinstance(orb_val, str):
                    return abs(float(orb_val.replace('°', '').strip()))
                return abs(float(orb_val))
            except (ValueError, TypeError):
                return 999.0
        
        sorted_s_aspects = sorted(
            s_aspects,
            key=lambda a: (-parse_score(a.get('score', 0)), parse_orb(a.get('orb', 999)))
        )[:2]
        
        snapshot["tightest_aspects"]["sidereal"] = [
            {
                "p1": a.get('p1_name', ''),
                "p2": a.get('p2_name', ''),
                "type": a.get('type', ''),
                "orb": a.get('orb', ''),
                "score": a.get('score', '')
            }
            for a in sorted_s_aspects
        ]
    
    # Get 2 tightest aspects from tropical
    t_aspects = chart_data.get('tropical_aspects', [])
    if t_aspects:
        def parse_score(score_val):
            try:
                if isinstance(score_val, str):
                    return float(score_val)
                return float(score_val)
            except (ValueError, TypeError):
                return 0.0
        
        def parse_orb(orb_val):
            try:
                if isinstance(orb_val, str):
                    return abs(float(orb_val.replace('°', '').strip()))
                return abs(float(orb_val))
            except (ValueError, TypeError):
                return 999.0
        
        sorted_t_aspects = sorted(
            t_aspects,
            key=lambda a: (-parse_score(a.get('score', 0)), parse_orb(a.get('orb', 999)))
        )[:2]
        
        snapshot["tightest_aspects"]["tropical"] = [
            {
                "p1": a.get('p1_name', ''),
                "p2": a.get('p2_name', ''),
                "type": a.get('type', ''),
                "orb": a.get('orb', ''),
                "score": a.get('score', '')
            }
            for a in sorted_t_aspects
        ]
    
    # Get stelliums from sidereal
    s_patterns = chart_data.get('sidereal_aspect_patterns', [])
    stelliums_s = [p for p in s_patterns if 'stellium' in p.get('description', '').lower()]
    snapshot["stelliums"]["sidereal"] = [p.get('description', '') for p in stelliums_s]
    
    # Get stelliums from tropical
    t_patterns = chart_data.get('tropical_aspect_patterns', [])
    stelliums_t = [p for p in t_patterns if 'stellium' in p.get('description', '').lower()]
    snapshot["stelliums"]["tropical"] = [p.get('description', '') for p in stelliums_t]
    
    return snapshot


def format_snapshot_for_prompt(snapshot: dict) -> str:
    """Format the snapshot data as a human-readable string for LLM prompts."""
    lines = []
    
    lines.append("=== SNAPSHOT CHART DATA ===")
    lines.append(f"Unknown Time: {snapshot.get('metadata', {}).get('unknown_time', False)}")
    lines.append("")
    
    # Core Identity
    lines.append("=== CORE IDENTITY ===")
    unknown_time = snapshot.get('metadata', {}).get('unknown_time', False)
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        core = snapshot.get('core_identity', {}).get(system, {})
        # Always include Sun and Moon
        for body in ['sun', 'moon']:
            if body in core:
                info = core[body]
                house_str = f", House {info['house']}" if info.get('house') and not unknown_time else ""
                retro_str = " (Rx)" if info.get('retrograde') else ""
                degree_str = f" {info.get('degree', 0)}°" if info.get('degree') else ""
                lines.append(f"  {body.capitalize()}: {info.get('sign', 'N/A')}{degree_str}{house_str}{retro_str}")
        # Only include Ascendant if time is known
        if not unknown_time and 'ascendant' in core:
            info = core['ascendant']
            degree_str = f" {info.get('degree', 0)}°" if info.get('degree') else ""
            lines.append(f"  Ascendant: {info.get('sign', 'N/A')}{degree_str}")
        elif unknown_time:
            lines.append("  Ascendant: Not available (birth time unknown)")
    lines.append("")
    
    # Tightest Aspects
    lines.append("=== TWO TIGHTEST ASPECTS ===")
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        aspects = snapshot.get('tightest_aspects', {}).get(system, [])
        if aspects:
            for a in aspects:
                lines.append(f"  {a.get('p1')} {a.get('type')} {a.get('p2')} (orb: {a.get('orb')}, score: {a.get('score')})")
        else:
            lines.append("  No aspects available")
    lines.append("")
    
    # Stelliums
    lines.append("=== STELLIUMS ===")
    for system in ['sidereal', 'tropical']:
        lines.append(f"\n{system.upper()}:")
        stelliums = snapshot.get('stelliums', {}).get(system, [])
        if stelliums:
            for s in stelliums:
                lines.append(f"  {s}")
        else:
            lines.append("  No stelliums detected")
    lines.append("")
    
    return "\n".join(lines)


async def generate_snapshot_reading(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate a comprehensive snapshot reading using limited data:
    - 2 tightest aspects (sidereal and tropical)
    - Stelliums (sidereal and tropical)
    - Sun, Moon, Rising (sidereal and tropical)
    
    This is blinded - no name, birthdate, or location is included.
    """
    if not GEMINI_API_KEY and AI_MODE != "stub":
        logger.warning("Gemini API key not configured - snapshot reading unavailable")
        return "Snapshot reading is temporarily unavailable."
    
    try:
        # Serialize snapshot data
        logger.info("Serializing snapshot data...")
        snapshot = serialize_snapshot_data(chart_data, unknown_time)
        
        # Validate snapshot has data
        if not snapshot.get("core_identity", {}).get("sidereal") and not snapshot.get("core_identity", {}).get("tropical"):
            logger.error("Snapshot data is empty - no core identity found")
            return "Snapshot reading is temporarily unavailable - chart data incomplete."
        
        snapshot_summary = format_snapshot_for_prompt(snapshot)
        logger.info(f"Snapshot summary length: {len(snapshot_summary)} characters")
        
        llm = Gemini3Client()
        logger.info("Calling Gemini API for snapshot reading...")
        
        unknown_time_flag = snapshot.get('metadata', {}).get('unknown_time', False)
        
        time_restrictions = ""
        if unknown_time_flag:
            time_restrictions = """
CRITICAL: Birth time is UNKNOWN. You MUST:
- Do NOT mention the Ascendant (Rising sign) at all - it is not available
- Do NOT mention house placements or house numbers
- Do NOT mention the Midheaven (MC) or any angles
- Do NOT mention chart ruler or house rulers
- Focus ONLY on sign placements, planetary aspects, and stelliums in signs
- When describing stelliums, focus on the sign energy, NOT house placement
- If the data shows "Unknown Time: True", the Ascendant/Rising is NOT in the data and should not be referenced"""
        else:
            time_restrictions = """
- You may reference the Ascendant (Rising sign) if it's in the data
- You may mention house placements if they're provided in the data"""
        
        system_prompt = f"""You are a master astrological analyst providing a comprehensive snapshot reading.

Your task is to synthesize the core identity (Sun, Moon, Rising if available), the two tightest aspects, and any stelliums from BOTH sidereal and tropical systems into a detailed but focused snapshot.

GUIDELINES:
1. Compare and contrast sidereal vs tropical placements - note where they align and where they differ
2. Explain how the tightest aspects create core dynamics in the personality
3. Describe how stelliums concentrate energy in specific signs (and houses only if birth time is known)
4. Synthesize these elements into a coherent picture of the person's core nature
5. Be specific and insightful, providing meaningful depth (4-6 paragraphs)
6. Use second person ("you", "your")
7. Focus on psychological patterns and tendencies, not predictions
8. Draw connections between the different elements to create a unified narrative
{time_restrictions}

OUTPUT FORMAT:
Provide a comprehensive snapshot reading in 4-6 paragraphs that synthesizes all the provided information with depth and insight."""
        
        unknown_time_flag = snapshot.get('metadata', {}).get('unknown_time', False)
        
        rising_instruction = ""
        if unknown_time_flag:
            rising_instruction = "\nIMPORTANT: The birth time is unknown, so the Ascendant/Rising sign is NOT available. Do NOT mention it or try to interpret it. Focus only on Sun and Moon placements, aspects, and stelliums."
        else:
            rising_instruction = "\nYou may include the Ascendant/Rising sign in your analysis if it's provided in the data."
        
        user_prompt = f"""Chart Snapshot Data:
{snapshot_summary}

Generate a comprehensive snapshot reading that:
1. Synthesizes the Sun and Moon placements from both sidereal and tropical systems, noting similarities and differences{rising_instruction}
2. Explains how the two tightest aspects from each system create core dynamics and psychological patterns
3. Describes how any stelliums concentrate energy in signs and what this means for the person's focus and expression (mention houses ONLY if birth time is known)
4. Compares and contrasts sidereal vs tropical where relevant, explaining the significance of any differences
5. Creates a coherent, detailed picture of the core psychological patterns, motivations, and tendencies
6. Draws meaningful connections between all the elements to tell a unified story

{"REMINDER: Birth time is unknown. Do NOT mention Ascendant, Rising sign, houses, Midheaven, or any time-sensitive chart elements." if unknown_time_flag else ""}

Provide 4-6 paragraphs of insightful, specific analysis that gives readers a meaningful understanding while they wait for their full report."""
        
        response = await llm.generate(
            system=system_prompt,
            user=user_prompt,
            max_output_tokens=4000,  # Increased for more comprehensive reading
            temperature=0.7,  # Higher for more creative and nuanced responses
            call_label="snapshot_reading"
        )
        
        return response.strip()
        
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Error generating snapshot reading: {error_type}: {error_msg}", exc_info=True)
        logger.error(f"Full error details - Type: {error_type}, Message: {error_msg}")
        return f"Snapshot reading is temporarily unavailable. Error: {error_type}"


async def get_gemini3_reading(chart_data: dict, unknown_time: bool, db: Session = None) -> str:
    """Four-call Gemini 3 pipeline with optional famous people section."""
    import time
    reading_start_time = time.time()
    
    if not GEMINI_API_KEY and AI_MODE != "stub":
        logger.error("Gemini API key not configured - AI reading unavailable")
        raise Exception("Gemini API key not configured. AI reading is unavailable.")
    
    logger.info("="*80)
    logger.info("="*80)
    logger.info("FULL READING GENERATION - STARTING")
    logger.info("="*80)
    logger.info("="*80)
    logger.info(f"AI_MODE: {AI_MODE}")
    logger.info(f"Unknown time: {unknown_time}")
    logger.info(f"Database session available: {db is not None}")
    logger.info("="*80)
    
    llm = Gemini3Client()
    
    try:
        # Step 0: Serialize chart data
        logger.info("Preparing chart data for LLM...")
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=unknown_time)
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
        logger.info(f"Chart serialized - Summary length: {len(chart_summary)} characters")
        logger.info("="*80)
        
        # Step 1: Global Blueprint
        blueprint = await g0_global_blueprint(llm, serialized_chart, chart_summary, unknown_time)
        
        # Step 2: Natal Foundation
        natal_sections = await g1_natal_foundation(llm, serialized_chart, chart_summary, blueprint, unknown_time)
        
        # Step 3: Deep Dive Chapters
        deep_sections = await g2_deep_dive_chapters(llm, serialized_chart, chart_summary, blueprint, natal_sections, unknown_time)
        
        # Step 4: Combine and Polish
        full_draft = f"{natal_sections}\n\n{deep_sections}"
        logger.info(f"Combined draft length: {len(full_draft)} characters")
        final_reading = await g3_polish_full_reading(llm, full_draft, chart_summary)
        
        # Step 5: Generate famous people section if database session is available
        famous_people_section = ""
        if db:
            try:
                logger.info("="*80)
                logger.info("FAMOUS PEOPLE MATCHING - STARTING")
                logger.info("="*80)
                logger.info("Calling find_similar_famous_people_internal to find matches...")
                famous_start = time.time()
                famous_people_matches = await find_similar_famous_people_internal(chart_data, limit=8, db=db)
                famous_duration = time.time() - famous_start
                logger.info(f"Famous people matching completed in {famous_duration:.2f} seconds")
                logger.info(f"find_similar_famous_people_internal returned: {famous_people_matches.get('matches_found', 0)} matches out of {famous_people_matches.get('total_compared', 0)} compared")
                
                if famous_people_matches and len(famous_people_matches.get('matches', [])) > 0:
                    logger.info(f"Found {len(famous_people_matches['matches'])} famous people matches, generating section...")
                    famous_people_section = await g4_famous_people_section(
                        llm, serialized_chart, chart_summary, famous_people_matches['matches'], unknown_time
                    )
                    final_reading = f"{final_reading}\n\n{famous_people_section}"
                    logger.info(f"Famous people section added - Final reading length: {len(final_reading)} characters")
                else:
                    logger.info("No famous people matches found or empty result")
                logger.info("="*80)
            except Exception as e:
                logger.error(f"Error generating famous people section: {e}", exc_info=True)
                # Continue without famous people section
        
        # Finalize reading
        final_reading = sanitize_reading_text(final_reading).strip()
        reading_duration = time.time() - reading_start_time
        
        # Calculate final costs
        summary = llm.get_summary()
        cost_info = calculate_gemini3_cost(summary['total_prompt_tokens'], summary['total_completion_tokens'])
        
        # Comprehensive cost summary
        logger.info("="*80)
        logger.info("="*80)
        logger.info("FULL READING GENERATION - COMPLETE")
        logger.info("="*80)
        logger.info("="*80)
        logger.info(f"Total Generation Time: {reading_duration:.2f} seconds ({reading_duration/60:.2f} minutes)")
        logger.info(f"Final Reading Length: {len(final_reading):,} characters")
        logger.info("")
        logger.info("=== GEMINI 3 API USAGE SUMMARY ===")
        logger.info(f"Total API Calls: {summary['call_count']}")
        logger.info(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        logger.info(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info("")
        logger.info("=== GEMINI 3 API COST BREAKDOWN ===")
        logger.info(f"Input Cost:  ${cost_info['input_cost_usd']:.6f} USD")
        logger.info(f"Output Cost: ${cost_info['output_cost_usd']:.6f} USD")
        logger.info(f"───────────────────────────────────")
        logger.info(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f} USD")
        logger.info("="*80)
        logger.info("="*80)
        
        # Also print to stdout for Render visibility
        print(f"\n{'='*80}")
        print("FULL READING GENERATION - COMPLETE")
        print(f"{'='*80}")
        print(f"Total Generation Time: {reading_duration:.2f} seconds ({reading_duration/60:.2f} minutes)")
        print(f"Final Reading Length: {len(final_reading):,} characters")
        print("")
        print("=== GEMINI 3 API USAGE SUMMARY ===")
        print(f"Total API Calls: {summary['call_count']}")
        print(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        print(f"Total Tokens: {summary['total_tokens']:,}")
        print("")
        print("=== GEMINI 3 API COST BREAKDOWN ===")
        print(f"Input Cost:  ${cost_info['input_cost_usd']:.6f} USD")
        print(f"Output Cost: ${cost_info['output_cost_usd']:.6f} USD")
        print(f"───────────────────────────────────")
        print(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f} USD")
        print(f"{'='*80}\n")
        
        return final_reading
    except Exception as e:
        reading_duration = time.time() - reading_start_time
        logger.error(f"Error during Gemini 3 reading generation after {reading_duration:.2f} seconds: {e}", exc_info=True)
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")


def sanitize_reading_text(text: str) -> str:
    """Remove leftover markdown markers or decorative separators from AI output."""
    if not text:
        return text
    
    patterns = [
        (r'\*\*\*(.*?)\*\*\*', r'\1'),
        (r'\*\*(.*?)\*\*', r'\1'),
        (r'\*(.*?)\*', r'\1'),
    ]
    cleaned = text
    for pattern, repl in patterns:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.DOTALL)
    
    # Remove standalone lines of asterisks or dashes
    cleaned = re.sub(r'^\s*(\*{3,}|-{3,})\s*$', '', cleaned, flags=re.MULTILINE)
    
    # Collapse multiple blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned


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


def send_snapshot_email_via_sendgrid(snapshot_text: str, recipient_email: str, chart_name: str, birth_date: str, birth_time: str, location: str):
    """Send snapshot reading email via SendGrid (text only, no PDF)."""
    if not SENDGRID_API_KEY or not SENDGRID_FROM_EMAIL:
        logger.warning("SendGrid not configured - cannot send snapshot email")
        return False
    
    try:
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=recipient_email,
            subject=f"Chart Snapshot: {chart_name}",
            html_content=f"""
            <html>
            <body>
                <h2>Your Chart Snapshot</h2>
                <p><strong>Name:</strong> {chart_name}</p>
                <p><strong>Birth Date:</strong> {birth_date}</p>
                <p><strong>Birth Time:</strong> {birth_time}</p>
                <p><strong>Location:</strong> {location}</p>
                <hr>
                <div style="white-space: pre-wrap;">{snapshot_text.replace(chr(10), '<br>')}</div>
            </body>
            </html>
            """
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 202]:
            logger.info(f"Snapshot email sent successfully to {recipient_email}")
            return True
        else:
            logger.error(f"SendGrid returned status {response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending snapshot email: {e}", exc_info=True)
        return False


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
    import time
    task_start_time = time.time()
    
    try:
        logger.info("="*80)
        logger.info("="*80)
        logger.info("BACKGROUND TASK: READING GENERATION & EMAIL SENDING")
        logger.info("="*80)
        logger.info("="*80)
        chart_name = user_inputs.get('full_name', 'N/A')
        user_email = user_inputs.get('user_email')
        # Strip whitespace if email is provided
        if user_email and isinstance(user_email, str):
            user_email = user_email.strip() or None  # Convert empty string to None
        
        logger.info(f"Chart Name: {chart_name}")
        logger.info(f"User Email: {user_email if user_email else 'Not provided'}")
        logger.info(f"Unknown Time: {unknown_time}")
        logger.info("="*80)
        logger.info("Starting AI reading generation...")
        logger.info("="*80)
        
        # Generate the reading
        try:
            reading_start = time.time()
            # Get database session for famous people matching
            from database import SessionLocal
            db = SessionLocal()
            try:
                reading_text = await get_gemini3_reading(chart_data, unknown_time, db=db)
            finally:
                db.close()
            
            reading_duration = time.time() - reading_start
            logger.info("="*80)
            logger.info(f"AI Reading successfully generated for: {chart_name}")
            logger.info(f"Reading generation time: {reading_duration:.2f} seconds ({reading_duration/60:.2f} minutes)")
            logger.info(f"Reading length: {len(reading_text):,} characters")
            logger.info("="*80)
            
            # Store reading in cache for frontend retrieval
            chart_hash = generate_chart_hash(chart_data, unknown_time)
            reading_cache[chart_hash] = {
                'reading': reading_text,
                'timestamp': datetime.now(),
                'chart_name': chart_name
            }
            logger.info(f"Reading stored in cache with hash: {chart_hash}")
            
            # Also save reading to user's saved chart if user exists
            # If chart doesn't exist, create it automatically
            if user_email:
                try:
                    from database import SessionLocal
                    db = SessionLocal()
                    try:
                        # Find user by email
                        user = db.query(User).filter(User.email == user_email).first()
                        if user:
                            # Find saved chart by hash
                            saved_charts = db.query(SavedChart).filter(
                                SavedChart.user_id == user.id
                            ).all()
                            
                            matching_chart = None
                            for chart in saved_charts:
                                if chart.chart_data_json:
                                    try:
                                        saved_chart_data = json.loads(chart.chart_data_json)
                                        saved_chart_hash = generate_chart_hash(saved_chart_data, chart.unknown_time)
                                        if saved_chart_hash == chart_hash:
                                            matching_chart = chart
                                            break
                                    except Exception as e:
                                        logger.warning(f"Error checking chart hash: {e}")
                                        continue
                            
                            if matching_chart:
                                # Update existing chart with reading
                                matching_chart.ai_reading = reading_text
                                db.commit()
                                logger.info(f"Reading saved to existing chart ID {matching_chart.id} for user {user_email}")
                            else:
                                # Chart doesn't exist - create it automatically
                                # Extract birth data from chart_data or user_inputs
                                try:
                                    # Try to get birth data from chart_data metadata or user_inputs
                                    birth_year = None
                                    birth_month = None
                                    birth_day = None
                                    birth_hour = 12  # Default to noon
                                    birth_minute = 0
                                    birth_location = "Unknown"
                                    
                                    # Try to extract from chart_data
                                    if isinstance(chart_data, dict):
                                        # Check if chart_data has birth info directly
                                        if 'birth_year' in chart_data:
                                            birth_year = chart_data.get('birth_year')
                                            birth_month = chart_data.get('birth_month')
                                            birth_day = chart_data.get('birth_day')
                                            birth_hour = chart_data.get('birth_hour', 12)
                                            birth_minute = chart_data.get('birth_minute', 0)
                                            birth_location = chart_data.get('birth_location', 'Unknown')
                                        # Or check metadata
                                        elif 'metadata' in chart_data and isinstance(chart_data['metadata'], dict):
                                            metadata = chart_data['metadata']
                                            birth_year = metadata.get('birth_year')
                                            birth_month = metadata.get('birth_month')
                                            birth_day = metadata.get('birth_day')
                                            birth_hour = metadata.get('birth_hour', 12)
                                            birth_minute = metadata.get('birth_minute', 0)
                                            birth_location = metadata.get('birth_location', 'Unknown')
                                    
                                    # Fallback to user_inputs if available (primary source)
                                    if user_inputs:
                                        # Try to parse from birth_date string if present
                                        birth_date_str = user_inputs.get('birth_date', '')
                                        if birth_date_str:
                                            try:
                                                # Format: "MM/DD/YYYY" or "M/D/YYYY"
                                                parts = birth_date_str.split('/')
                                                if len(parts) == 3:
                                                    birth_month = int(parts[0])
                                                    birth_day = int(parts[1])
                                                    birth_year = int(parts[2])
                                            except Exception as date_error:
                                                logger.warning(f"Could not parse birth_date '{birth_date_str}': {date_error}")
                                        
                                        # Get location from user_inputs
                                        location_input = user_inputs.get('location', '')
                                        if location_input:
                                            birth_location = location_input
                                        
                                        # Get time from user_inputs if available
                                        birth_time_str = user_inputs.get('birth_time', '')
                                        if birth_time_str and not unknown_time:
                                            try:
                                                # Try to parse time string (format: "HH:MM AM/PM" or "H:MM AM/PM")
                                                birth_time_upper = birth_time_str.upper().strip()
                                                if ':' in birth_time_upper:
                                                    # Remove AM/PM and split
                                                    time_without_ampm = birth_time_upper.replace(' AM', '').replace(' PM', '').replace('AM', '').replace('PM', '')
                                                    time_parts = time_without_ampm.split(':')
                                                    if len(time_parts) >= 2:
                                                        hour = int(time_parts[0])
                                                        minute = int(time_parts[1])
                                                        # Handle PM
                                                        if 'PM' in birth_time_upper and hour < 12:
                                                            hour += 12
                                                        # Handle 12 AM (midnight)
                                                        elif 'AM' in birth_time_upper and hour == 12:
                                                            hour = 0
                                                        birth_hour = hour
                                                        birth_minute = minute
                                            except Exception as time_error:
                                                logger.warning(f"Could not parse birth_time '{birth_time_str}': {time_error}")
                                    
                                    # If we still don't have birth data, we can't create the chart
                                    if not birth_year or not birth_month or not birth_day:
                                        logger.warning(f"Cannot auto-save chart for {user_email}: missing birth data in chart_data or user_inputs")
                                    else:
                                        # Create new saved chart with reading
                                        new_chart = SavedChart(
                                            user_id=user.id,
                                            chart_name=chart_name,
                                            birth_year=birth_year,
                                            birth_month=birth_month,
                                            birth_day=birth_day,
                                            birth_hour=birth_hour if not unknown_time else 12,
                                            birth_minute=birth_minute if not unknown_time else 0,
                                            birth_location=birth_location,
                                            unknown_time=unknown_time,
                                            chart_data_json=json.dumps(chart_data),
                                            ai_reading=reading_text
                                        )
                                        db.add(new_chart)
                                        db.commit()
                                        db.refresh(new_chart)
                                        logger.info(f"New chart created and reading saved (ID: {new_chart.id}) for user {user_email}")
                                except Exception as create_error:
                                    logger.warning(f"Could not create new chart for reading: {create_error}")
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"Could not save reading to chart: {e}")
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
        
        # Final task summary
        task_duration = time.time() - task_start_time
        logger.info("="*80)
        logger.info("="*80)
        logger.info("BACKGROUND TASK - COMPLETE")
        logger.info("="*80)
        logger.info("="*80)
        logger.info(f"Chart Name: {chart_name}")
        logger.info(f"Total Task Duration: {task_duration:.2f} seconds ({task_duration/60:.2f} minutes)")
        logger.info(f"Reading Length: {len(reading_text):,} characters")
        logger.info(f"User Email: {user_email if user_email else 'Not provided'}")
        logger.info(f"User Email Sent: {'Yes' if user_email else 'No'}")
        logger.info(f"Admin Email Sent: {'Yes' if ADMIN_EMAIL else 'No'}")
        logger.info("="*80)
        logger.info("="*80)
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
@limiter.limit("200/day")
async def calculate_chart_endpoint(
    request: Request, 
    data: ChartRequest, 
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
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

        # Geocoding with fallback: Try OpenCage first, then Nominatim
        lat, lng, timezone_name = None, None, None
        
        # Try OpenCage first (if key is available)
        opencage_key = os.getenv("OPENCAGE_KEY")
        if opencage_key:
            try:
                geo_url = f"https://api.opencagedata.com/geocode/v1/json?q={data.location}&key={opencage_key}"
                response = requests.get(geo_url, timeout=10)
                
                # Check for 402 Payment Required - don't fail, just fall back
                if response.status_code == 402:
                    logger.warning("OpenCage API returned 402 Payment Required. Falling back to Nominatim.")
                else:
                    response.raise_for_status()
                    geo_res = response.json()
                    results = geo_res.get("results", [])
                    if results:
                        result = results[0]
                        geometry = result.get("geometry", {})
                        annotations = result.get("annotations", {}).get("timezone", {})
                        lat = geometry.get("lat")
                        lng = geometry.get("lng")
                        timezone_name = annotations.get("name")
            except requests.exceptions.RequestException as e:
                logger.warning(f"OpenCage geocoding failed: {e}. Falling back to Nominatim.")
        
        # Fallback to Nominatim if OpenCage failed or returned 402
        if not lat or not lng:
            try:
                nominatim_url = "https://nominatim.openstreetmap.org/search"
                params = {
                    "q": data.location,
                    "format": "json",
                    "limit": 1
                }
                headers = {
                    "User-Agent": "SynthesisAstrology/1.0 (contact@example.com)"  # Required by Nominatim
                }
                response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                nominatim_data = response.json()
                
                if nominatim_data and len(nominatim_data) > 0:
                    result_data = nominatim_data[0]
                    lat = float(result_data.get("lat", 0))
                    lng = float(result_data.get("lon", 0))
                    
                    # Nominatim doesn't provide timezone directly, so we'll use a timezone lookup
                    # Use a free timezone API
                    if lat and lng:
                        try:
                            # Use timezone lookup API
                            tz_url = f"https://timeapi.io/api/TimeZone/coordinate?latitude={lat}&longitude={lng}"
                            tz_response = requests.get(tz_url, timeout=5)
                            if tz_response.status_code == 200:
                                tz_data = tz_response.json()
                                timezone_name = tz_data.get("timeZone", "UTC")
                            else:
                                # Fallback: use UTC and let pendulum handle it
                                timezone_name = "UTC"
                        except Exception as tz_e:
                            logger.warning(f"Timezone lookup failed: {tz_e}. Using UTC.")
                            timezone_name = "UTC"
            except requests.exceptions.RequestException as e:
                logger.error(f"Nominatim geocoding failed: {e}")
                raise HTTPException(status_code=400, detail=f"Could not find location data for '{data.location}'. Please be more specific (e.g., City, State, Country).")
        
        # Final validation
        if not lat or not lng:
            raise HTTPException(status_code=400, detail=f"Could not find location data for '{data.location}'. Please be more specific (e.g., City, State, Country).")
        
        if not timezone_name:
            timezone_name = "UTC"  # Fallback to UTC

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
        # Only calculate name numerology if user confirms it's their full birth name
        if data.is_full_birth_name and len(name_parts) >= 2:
            try:
                name_numerology = calculate_name_numerology(data.full_name)
                logger.info(f"Calculated name numerology for full birth name: {data.full_name}")
            except Exception as e:
                logger.warning(f"Could not calculate name numerology for '{data.full_name}': {e}")
                name_numerology = None  # Ensure it's None if calculation fails
        elif not data.is_full_birth_name:
            logger.info(f"Skipping name numerology - user did not confirm full birth name")
            
        chinese_zodiac = get_chinese_zodiac_and_element(data.year, data.month, data.day)
        
        full_response = chart.get_full_chart_data(numerology, name_numerology, chinese_zodiac, data.unknown_time)
        
        # Add quick highlights to the response
        try:
            quick_highlights = get_quick_highlights(full_response, data.unknown_time)
            full_response["quick_highlights"] = quick_highlights
        except Exception as e:
            logger.warning(f"Could not generate quick highlights: {e}")
            full_response["quick_highlights"] = "Quick highlights are unavailable for this chart."
        
        # Generate snapshot reading (blinded, limited data) - only for actual birth charts, not transit charts
        # Skip for transit charts to avoid blocking the response
        # Use timeout to prevent blocking chart response for too long
        is_transit_chart = data.full_name.lower() in ["current transits", "transits"]
        if not is_transit_chart:
            logger.info("Generating snapshot reading...")
            try:
                # Add timeout of 60 seconds - allows for comprehensive reading generation
                # Increased from 30s to handle slower API responses
                snapshot_reading = await asyncio.wait_for(
                    generate_snapshot_reading(full_response, data.unknown_time),
                    timeout=60.0
                )
                # Always set snapshot_reading (even if it's an error message, so user knows what happened)
                full_response["snapshot_reading"] = snapshot_reading
                logger.info(f"Snapshot reading generated successfully (length: {len(snapshot_reading) if snapshot_reading else 0})")
                
                # Send snapshot email immediately to user and admin (only if successful)
                if snapshot_reading and snapshot_reading != "Snapshot reading is temporarily unavailable.":
                    try:
                        # Format birth date and time for email
                        birth_date_str = f"{data.month}/{data.day}/{data.year}"
                        if data.unknown_time:
                            birth_time_str = "Unknown (Noon Chart)"
                        else:
                            birth_time_str = f"{data.hour:02d}:{data.minute:02d}"
                            if data.hour >= 12:
                                birth_time_str += " PM"
                            else:
                                birth_time_str += " AM"
                        
                        # Send to user (if email provided)
                        if data.user_email:
                            send_snapshot_email_via_sendgrid(
                                snapshot_reading,
                                data.user_email,
                                data.full_name,
                                birth_date_str,
                                birth_time_str,
                                data.location
                            )
                        
                        # Send to admin (always, if configured)
                        if ADMIN_EMAIL:
                            send_snapshot_email_via_sendgrid(
                                snapshot_reading,
                                ADMIN_EMAIL,
                                data.full_name,
                                birth_date_str,
                                birth_time_str,
                                data.location
                            )
                    except Exception as email_error:
                        logger.warning(f"Failed to send snapshot email: {email_error}")
                
            except asyncio.TimeoutError:
                logger.error("Snapshot reading generation timed out after 60 seconds - skipping to avoid blocking chart response")
                full_response["snapshot_reading"] = "Snapshot reading timed out. Please try again or wait for your full reading."
            except Exception as e:
                logger.error(f"Could not generate snapshot reading: {e}", exc_info=True)
                # Return error message instead of None so user knows what happened
                full_response["snapshot_reading"] = f"Snapshot reading temporarily unavailable: {str(e)}"
        else:
            # For transit charts, don't include snapshot reading
            full_response["snapshot_reading"] = None
        
        # Automatically generate full reading for FRIENDS_AND_FAMILY_KEY users
        # Check both query params and headers (case-insensitive)
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            # Check headers (case-insensitive)
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key:
            logger.info(f"FRIENDS_AND_FAMILY_KEY received (length: {len(friends_and_family_key)}, first 3 chars: {friends_and_family_key[:3] if len(friends_and_family_key) >= 3 else friends_and_family_key})")
            logger.info(f"ADMIN_SECRET_KEY configured: {bool(ADMIN_SECRET_KEY)}, length: {len(ADMIN_SECRET_KEY) if ADMIN_SECRET_KEY else 0}")
            if ADMIN_SECRET_KEY and friends_and_family_key == ADMIN_SECRET_KEY:
                # Check if this is a transit chart (skip for those)
                if not is_transit_chart and data.user_email:
                    logger.info(f"FRIENDS_AND_FAMILY_KEY detected - automatically generating full reading for {data.full_name}")
                    # Generate chart hash for polling
                    chart_hash = generate_chart_hash(full_response, data.unknown_time)
                    
                    # Prepare user inputs for reading generation (include birth data for auto-saving)
                    # Format time in 12-hour format for user_inputs
                    if not data.unknown_time:
                        hour_12 = data.hour % 12
                        if hour_12 == 0:
                            hour_12 = 12
                        am_pm = 'AM' if data.hour < 12 else 'PM'
                        birth_time_str = f"{hour_12}:{data.minute:02d} {am_pm}"
                    else:
                        birth_time_str = ''
                    
                    user_inputs = {
                        'full_name': data.full_name,
                        'user_email': data.user_email,
                        'birth_date': f"{data.month}/{data.day}/{data.year}",
                        'birth_time': birth_time_str,
                        'location': data.location
                    }
                    
                    # Queue full reading generation in background
                    background_tasks.add_task(
                        generate_reading_and_send_email,
                        chart_data=full_response,
                        unknown_time=data.unknown_time,
                        user_inputs=user_inputs
                    )
                    
                    # Add chart_hash to response so frontend can poll for reading
                    full_response["chart_hash"] = chart_hash
                    full_response["full_reading_queued"] = True
                    logger.info(f"Full reading queued for FRIENDS_AND_FAMILY_KEY user with chart_hash: {chart_hash}")
        
        # Generate chart_hash for all charts (needed for full reading page)
        chart_hash = generate_chart_hash(full_response, data.unknown_time)
        full_response["chart_hash"] = chart_hash
        
        # Auto-save chart if user is logged in
        if current_user:
            try:
                # Check if chart already exists for this user
                existing_chart = db.query(SavedChart).filter(
                    SavedChart.user_id == current_user.id,
                    SavedChart.chart_name == data.full_name,
                    SavedChart.birth_year == data.year,
                    SavedChart.birth_month == data.month,
                    SavedChart.birth_day == data.day,
                    SavedChart.birth_location == data.location
                ).first()
                
                if not existing_chart:
                    # Auto-save the chart
                    saved_chart = SavedChart(
                        user_id=current_user.id,
                        chart_name=data.full_name,
                        birth_year=data.year,
                        birth_month=data.month,
                        birth_day=data.day,
                        birth_hour=data.hour if not data.unknown_time else 12,
                        birth_minute=data.minute if not data.unknown_time else 0,
                        birth_location=data.location,
                        unknown_time=data.unknown_time,
                        chart_data_json=json.dumps(full_response)
                    )
                    db.add(saved_chart)
                    db.commit()
                    db.refresh(saved_chart)
                    logger.info(f"Chart auto-saved for user {current_user.email}: {data.full_name} (ID: {saved_chart.id})")
                    full_response["saved_chart_id"] = saved_chart.id
                else:
                    logger.info(f"Chart already exists for user {current_user.email}: {data.full_name} (ID: {existing_chart.id})")
                    full_response["saved_chart_id"] = existing_chart.id
            except Exception as e:
                logger.warning(f"Could not auto-save chart for user {current_user.email}: {e}", exc_info=True)
                # Don't fail the request if auto-save fails
            
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
async def generate_reading_endpoint(
    request: Request, 
    reading_data: ReadingRequest, 
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    This endpoint queues the reading generation and email sending in the background.
    Returns immediately so users can close the browser and still receive their reading via email.
    Requires active subscription (or admin bypass).
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
        
        # Check for FRIENDS_AND_FAMILY_KEY (for logging purposes)
        # Check both query params and headers (case-insensitive)
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            # Check headers (case-insensitive)
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key:
            logger.info(f"[generate_reading] FRIENDS_AND_FAMILY_KEY received (length: {len(friends_and_family_key)}, first 3 chars: {friends_and_family_key[:3] if len(friends_and_family_key) >= 3 else friends_and_family_key})")
            logger.info(f"[generate_reading] ADMIN_SECRET_KEY configured: {bool(ADMIN_SECRET_KEY)}, length: {len(ADMIN_SECRET_KEY) if ADMIN_SECRET_KEY else 0}")
        
        # Subscription checks removed - all users can access full readings
        # FRIENDS_AND_FAMILY_KEY still works for logging purposes
        has_access, reason = check_subscription_access(current_user, db, friends_and_family_key)
        if friends_and_family_key:
            logger.info(f"[generate_reading] Access check result: has_access={has_access}, reason={reason}")
        
        # Log successful admin bypass if used (works even without logged-in user)
        if reason == "admin_bypass":
            try:
                user_email_for_log = current_user.email if current_user else user_email
                log_entry = AdminBypassLog(
                    user_email=user_email_for_log,
                    endpoint="/generate_reading",
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent"),
                    details=f"Admin bypass used for full reading generation" + (f" by user {user_email_for_log}" if user_email_for_log else " (anonymous)")
                )
                db.add(log_entry)
                db.commit()
            except Exception as log_error:
                # Handle sequence sync issues gracefully
                error_str = str(log_error)
                if "UniqueViolation" in error_str and "admin_bypass_logs_pkey" in error_str:
                    logger.warning(f"Admin bypass log sequence out of sync. Run fix_admin_logs_sequence.py to resolve. Error: {log_error}")
                    # Try to rollback and continue - logging failure shouldn't block the request
                    try:
                        db.rollback()
                    except:
                        pass
                else:
                    logger.warning(f"Could not log admin bypass: {log_error}")
        
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
@limiter.limit("500/hour")
async def get_reading_endpoint(
    request: Request, 
    chart_hash: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Retrieve a completed reading from the cache by chart hash.
    Used by frontend to poll for completed readings.
    Requires authentication to access full reading page.
    """
    # Require authentication for full reading access
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required to access full reading")
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
        
        # Try to find saved chart by hash (for chat functionality)
        chart_id = None
        try:
            # Look for saved chart with matching hash
            saved_charts = db.query(SavedChart).filter(
                SavedChart.user_id == current_user.id
            ).all()
            
            for chart in saved_charts:
                if chart.chart_data_json:
                    try:
                        chart_data = json.loads(chart.chart_data_json)
                        chart_data_hash = generate_chart_hash(chart_data, chart.unknown_time)
                        if chart_data_hash == chart_hash:
                            chart_id = chart.id
                            break
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Could not find chart by hash: {e}")
        
        return {
            "status": "completed",
            "reading": cached_data['reading'],
            "chart_name": cached_data.get('chart_name', 'N/A'),
            "chart_id": chart_id
        }
    else:
        # Check if reading exists in saved chart
        try:
            saved_charts = db.query(SavedChart).filter(
                SavedChart.user_id == current_user.id,
                SavedChart.ai_reading.isnot(None)
            ).all()
            
            for chart in saved_charts:
                if chart.chart_data_json:
                    try:
                        chart_data = json.loads(chart.chart_data_json)
                        chart_data_hash = generate_chart_hash(chart_data, chart.unknown_time)
                        if chart_data_hash == chart_hash and chart.ai_reading:
                            return {
                                "status": "completed",
                                "reading": chart.ai_reading,
                                "chart_name": chart.chart_name,
                                "chart_id": chart.id
                            }
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Could not check saved charts: {e}")
        
        return {
            "status": "processing",
            "message": "Reading is still being generated. Please check again in a moment."
        }


# ============================================================
# USER AUTHENTICATION ENDPOINTS
# ============================================================

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/register", response_model=Token)
async def register_endpoint(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists."
            )
        
        # Validate password
        if len(data.password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long."
            )
        
        # Create the user
        user_create = UserCreate(
            email=data.email,
            password=data.password,
            full_name=data.full_name
        )
        user = create_user(db, user_create)
        
        # Create access token (sub must be a string for JWT)
        access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
        
        logger.info(f"New user registered: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )


@app.post("/auth/login", response_model=Token)
async def login_endpoint(data: LoginRequest, db: Session = Depends(get_db)):
    """Login and get access token."""
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="This account has been deactivated."
        )
    
    # Create access token (sub must be a string for JWT)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    logger.info(f"User logged in: {user.email}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_endpoint(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse.model_validate(current_user)


# ============================================================
# SAVED CHARTS ENDPOINTS
# ============================================================

class SaveChartRequest(BaseModel):
    chart_name: str
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_location: str
    unknown_time: bool = False
    chart_data_json: Optional[str] = None
    ai_reading: Optional[str] = None


class SavedChartResponse(BaseModel):
    id: int
    chart_name: str
    created_at: datetime
    birth_year: int
    birth_month: int
    birth_day: int
    birth_hour: int
    birth_minute: int
    birth_location: str
    unknown_time: bool
    has_reading: bool

    class Config:
        from_attributes = True


@app.post("/charts/save")
async def save_chart_endpoint(
    data: SaveChartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save a chart for the authenticated user."""
    # Create the saved chart
    saved_chart = SavedChart(
        user_id=current_user.id,
        chart_name=data.chart_name,
        birth_year=data.birth_year,
        birth_month=data.birth_month,
        birth_day=data.birth_day,
        birth_hour=data.birth_hour,
        birth_minute=data.birth_minute,
        birth_location=data.birth_location,
        unknown_time=data.unknown_time,
        chart_data_json=data.chart_data_json,
        ai_reading=data.ai_reading
    )
    db.add(saved_chart)
    db.commit()
    db.refresh(saved_chart)
    
    logger.info(f"Chart saved for user {current_user.email}: {data.chart_name}")
    
    return {
        "id": saved_chart.id,
        "message": "Chart saved successfully."
    }


@app.get("/charts/list")
async def list_charts_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all saved charts for the authenticated user."""
    charts = db.query(SavedChart).filter(SavedChart.user_id == current_user.id).order_by(SavedChart.created_at.desc()).all()
    
    return [
        {
            "id": chart.id,
            "chart_name": chart.chart_name,
            "created_at": chart.created_at.isoformat(),
            "birth_date": f"{chart.birth_month}/{chart.birth_day}/{chart.birth_year}",
            "birth_location": chart.birth_location,
            "unknown_time": chart.unknown_time,
            "has_reading": chart.ai_reading is not None
        }
        for chart in charts
    ]


@app.get("/charts/{chart_id}")
async def get_chart_endpoint(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific saved chart."""
    chart = db.query(SavedChart).filter(
        SavedChart.id == chart_id,
        SavedChart.user_id == current_user.id
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    return {
        "id": chart.id,
        "chart_name": chart.chart_name,
        "created_at": chart.created_at.isoformat(),
        "birth_year": chart.birth_year,
        "birth_month": chart.birth_month,
        "birth_day": chart.birth_day,
        "birth_hour": chart.birth_hour,
        "birth_minute": chart.birth_minute,
        "birth_location": chart.birth_location,
        "unknown_time": chart.unknown_time,
        "chart_data": json.loads(chart.chart_data_json) if chart.chart_data_json else None,
        "ai_reading": chart.ai_reading
    }


@app.delete("/charts/{chart_id}")
async def delete_chart_endpoint(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a saved chart."""
    chart = db.query(SavedChart).filter(
        SavedChart.id == chart_id,
        SavedChart.user_id == current_user.id
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    db.delete(chart)
    db.commit()
    
    logger.info(f"Chart deleted for user {current_user.email}: {chart.chart_name}")
    
    return {"message": "Chart deleted successfully."}


# ============================================================
# CHAT WITH GEMINI ENDPOINTS
# ============================================================

class ChatMessageRequest(BaseModel):
    chart_id: int
    message: str
    conversation_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str


class ChatConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessageResponse]


# System prompt for the chart astrologer chatbot
CHART_ASTROLOGER_SYSTEM_PROMPT = """You are a knowledgeable astrologer who helps people explore and understand their birth chart as a tool for self-reflection and personal insight.

IMPORTANT LEGAL DISCLAIMER - YOU MUST FOLLOW THESE RULES:
- You are providing astrological INTERPRETATION for ENTERTAINMENT and SELF-REFLECTION purposes only
- You are NOT a licensed professional in any field (medical, psychological, financial, legal, etc.)
- You do NOT give advice - you offer astrological perspectives and interpretations
- You ALWAYS defer to qualified professionals for any serious life decisions
- Astrology describes potentials and tendencies, NOT fixed outcomes or predictions
- The user has free will and is the author of their own life

CONTEXT:
You have access to this specific user's birth chart data, including both Sidereal and Tropical placements, aspects, house positions, numerology, and Chinese zodiac information. You also have access to their personalized reading that was created for them.

CRITICAL SECURITY NOTE:
- You are ONLY discussing the chart of the person you are speaking with
- The reading and chart data belongs to THIS logged-in user
- Never reference or discuss charts/readings of other users

YOUR ROLE:
1. Explain and interpret specific placements, aspects, or patterns in their chart
2. Reference their personalized reading when relevant
3. Help them understand astrological symbolism and how it may relate to their life
4. Discuss psychological patterns and tendencies suggested by their chart
5. Explore themes around personal growth, relationships, career, and meaning
6. Explain astrological concepts in accessible language

WHAT YOU DO NOT DO:
- You do NOT predict the future or specific outcomes
- You do NOT diagnose medical or psychological conditions
- You do NOT provide financial, legal, or medical advice
- You do NOT tell people what decisions to make
- You do NOT claim astrology is scientifically proven or deterministic

COMMUNICATION STYLE:
- Be warm and supportive, but not prescriptive
- Use reflective language: "your chart suggests," "this placement often correlates with," "you might find that," "some with this aspect experience"
- Present interpretations as possibilities for reflection, not facts
- Encourage self-exploration rather than dependence on the reading
- When discussing challenges, frame them as areas for self-awareness, not problems to fix
- Be specific to THEIR chart - avoid generic statements

WHEN ASKED ABOUT SERIOUS MATTERS:
- Health/Medical: "While your chart shows themes around [X], please consult a healthcare professional for any health concerns."
- Mental Health: "Astrology can offer perspective, but a licensed therapist or counselor is the right resource for mental health support."
- Financial: "Your chart suggests certain tendencies around resources, but please consult a financial professional for financial decisions."
- Legal: "I can discuss astrological themes, but please consult a qualified attorney for legal matters."
- Relationships: Discuss patterns and tendencies, but don't tell them what to do or whether to stay/leave.

Remember: Your purpose is to facilitate self-reflection and exploration through the symbolic language of astrology. You illuminate possibilities; the user decides what resonates and what to do with that understanding."""


async def get_gemini_chat_response(
    chart_data: dict,
    reading: Optional[str],
    conversation_history: List[dict],
    user_message: str,
    chart_name: str = "User",
    famous_matches: Optional[List[dict]] = None,
    db: Optional[Session] = None
) -> str:
    """Generate a chat response using Gemini based on the user's chart.
    
    SECURITY: This function receives chart data that has already been verified
    to belong to the authenticated user by the calling endpoint.
    """
    if not GEMINI_API_KEY and AI_MODE != "stub":
        raise Exception("Gemini API key not configured. Chat is unavailable.")
    
    llm = Gemini3Client()
    
    # Build context from chart data
    try:
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=chart_data.get('unknown_time', False))
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
    except Exception as e:
        logger.warning(f"Could not serialize chart for chat: {e}")
        chart_summary = json.dumps(chart_data, indent=2)
    
    # Build conversation context (last 10 messages for continuity)
    conversation_context = ""
    if conversation_history:
        conversation_context = "\n\n=== PREVIOUS CONVERSATION ===\n"
        for msg in conversation_history[-10:]:
            role = "User" if msg['role'] == 'user' else "Astrologer"
            conversation_context += f"{role}: {msg['content']}\n"
    
    # Include the COMPLETE personalized reading as context
    # This reading was generated specifically for this user's chart
    reading_context = ""
    if reading:
        reading_context = f"""

=== THIS USER'S COMPLETE PERSONALIZED READING ===
The following is the full AI-generated astrological reading created specifically for this chart owner.
Reference this reading when answering questions - it contains deep insights about their chart.

{reading}

=== END OF PERSONALIZED READING ===
"""
    
    # Include famous people matches (if available)
    # Also check if user is asking about a specific famous person and include their full chart data
    famous_matches_context = ""
    famous_person_chart_context = ""
    
    if famous_matches:
        top_famous = famous_matches[:10]  # limit for prompt size
        lines = ["", "=== FAMOUS PEOPLE MATCHES FOR THIS CHART ==="]
        for m in top_famous:
            name = m.get("name", "Unknown")
            occ = m.get("occupation") or ""
            score = m.get("similarity_score")
            score_str = f"{score}" if isinstance(score, (int, float)) else "N/A"
            factors = m.get("matching_factors", []) or []
            header = f"- {name} ({occ}) – synthesis score: {score_str}".strip()
            lines.append(header)
            if factors:
                lines.append(f"  Matching factors: {', '.join(factors)}")
        lines.append("=== END OF FAMOUS PEOPLE MATCHES ===")
        famous_matches_context = "\n".join(lines)
    
    # Check if user is asking about a specific famous person and fetch their full chart data
    if db and famous_matches:
        user_message_lower = user_message.lower()
        for match in famous_matches[:10]:  # Check top 10 matches
            famous_name = match.get("name", "").lower()
            if famous_name and famous_name in user_message_lower:
                # User is asking about this famous person - fetch their full chart data
                try:
                    from database import FamousPerson
                    # Get the FamousPerson object from database
                    fp = db.query(FamousPerson).filter(
                        FamousPerson.name.ilike(f"%{match.get('name')}%")
                    ).first()
                    
                    if fp and fp.chart_data_json:
                        fp_chart_data = json.loads(fp.chart_data_json)
                        # Serialize the famous person's chart for LLM
                        fp_serialized = serialize_chart_for_llm(
                            fp_chart_data, 
                            unknown_time=fp.unknown_time if hasattr(fp, 'unknown_time') else True
                        )
                        fp_chart_summary = format_serialized_chart_for_prompt(fp_serialized)
                        
                        famous_person_chart_context = f"""

=== FULL CHART DATA FOR {match.get('name').upper()} ===
You have access to the complete birth chart data for {match.get('name')} ({match.get('occupation', '')}).
This is their FULL chart data - use it to provide detailed comparisons when the user asks about them.

Birth Date: {match.get('birth_date', 'Unknown')}
Birth Location: {match.get('birth_location', 'Unknown')}

{fp_chart_summary}

=== END OF {match.get('name').upper()}'S CHART DATA ===
"""
                        logger.info(f"Including full chart data for {match.get('name')} in chat context")
                        break  # Only include the first matching famous person's chart
                except Exception as e:
                    logger.warning(f"Could not fetch full chart data for famous person: {e}")
                    # Continue without the full chart data
    
    user_prompt = f"""=== CHART OWNER ===
You are speaking directly with the chart owner about THEIR chart. All data below belongs to them.

=== CHART DATA ===
{chart_summary}
{reading_context}
{famous_matches_context}
{famous_person_chart_context}
{conversation_context}

=== USER'S CURRENT QUESTION ===
{user_message}

=== INSTRUCTIONS ===
Provide a helpful, personalized response that:
1. Addresses their specific question
2. References their chart placements and aspects when relevant
3. Quotes or paraphrases relevant parts of their reading if it applies to their question
4. Offers practical, actionable insights based on their unique astrological blueprint
5. Speaks directly to them as the owner of this chart
6. If the user is asking about a specific famous person, use the full chart data provided above to make detailed comparisons between their chart and the famous person's chart"""
    
    response = await llm.generate(
        system=CHART_ASTROLOGER_SYSTEM_PROMPT,
        user=user_prompt,
        max_output_tokens=2500,
        temperature=0.7,
        call_label="chart_chat"
    )
    
    return response


@app.post("/chat/send")
async def send_chat_message_endpoint(
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a chat message and get a response from the AI astrologer.
    
    SECURITY: Only allows access to charts owned by the authenticated user.
    The AI astrologer will only have context from this user's chart and reading.
    """
    # SECURITY: Verify chart belongs to authenticated user
    # This ensures users can only chat about their own charts
    chart = db.query(SavedChart).filter(
        SavedChart.id == data.chart_id,
        SavedChart.user_id == current_user.id  # Critical: ownership check
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    # Get or create conversation
    if data.conversation_id:
        conversation = db.query(ChatConversation).filter(
            ChatConversation.id == data.conversation_id,
            ChatConversation.user_id == current_user.id,
            ChatConversation.chart_id == chart.id
        ).first()
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        # Create new conversation
        conversation = ChatConversation(
            user_id=current_user.id,
            chart_id=chart.id,
            title=data.message[:50] + "..." if len(data.message) > 50 else data.message
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Get conversation history
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at).all()
    
    conversation_history = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]
    
    # Save user message
    user_msg = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=data.message
    )
    db.add(user_msg)
    
    # Commit with sequence fix handling
    try:
        db.commit()
    except IntegrityError as e:
        error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "UniqueViolation" in error_str and "chat_messages_pkey" in error_str:
            logger.warning(f"Chat messages sequence out of sync. Fixing sequence...")
            db.rollback()
            # Fix the sequence (only for PostgreSQL)
            try:
                from database import DATABASE_URL
                is_postgres = DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')
                
                if is_postgres:
                    # Get max ID from table
                    result = db.execute(text("SELECT MAX(id) FROM chat_messages"))
                    max_id = result.scalar() or 0
                    # Reset sequence to max_id + 1
                    db.execute(text(f"SELECT setval('chat_messages_id_seq', {max_id + 1}, false)"))
                    db.commit()
                    logger.info(f"Fixed chat_messages sequence. Next ID will be {max_id + 1}")
                    # Retry adding the message
                    db.add(user_msg)
                    db.commit()
                else:
                    # SQLite - recreate the message object
                    user_msg = ChatMessage(
                        conversation_id=conversation.id,
                        role="user",
                        content=data.message
                    )
                    db.add(user_msg)
                    db.commit()
            except Exception as fix_error:
                logger.error(f"Failed to fix chat_messages sequence: {fix_error}")
                raise HTTPException(status_code=500, detail="Database error. Please try again.")
        else:
            raise
    
    # Parse chart data
    chart_data = json.loads(chart.chart_data_json) if chart.chart_data_json else {}

    # Compute famous-people matches for this chart so chat AI can reference them
    famous_matches: List[dict] = []
    try:
        if chart_data:
            matches_result = await find_similar_famous_people_internal(
                chart_data=chart_data,
                limit=30,
                db=db,
            )
            famous_matches = matches_result.get("matches", []) or []
    except Exception as e:
        logger.warning(f"Could not compute famous people matches for chat context: {e}")

    try:
        # Get AI response - passing verified user's chart data and famous matches
        # Security: chart ownership already verified above (user_id check)
        ai_response = await get_gemini_chat_response(
            chart_data=chart_data,
            reading=chart.ai_reading,
            conversation_history=conversation_history,
            user_message=data.message,
            chart_name=chart.chart_name,
            famous_matches=famous_matches,
            db=db,
        )
        
        # Save AI response
        assistant_msg = ChatMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response
        )
        db.add(assistant_msg)
        
        # Update conversation timestamp
        conversation.updated_at = datetime.utcnow()
        
        # Commit with sequence fix handling
        try:
            db.commit()
        except IntegrityError as e:
            error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "UniqueViolation" in error_str and "chat_messages_pkey" in error_str:
                logger.warning(f"Chat messages sequence out of sync. Fixing sequence...")
                db.rollback()
                # Fix the sequence (only for PostgreSQL)
                try:
                    from database import DATABASE_URL
                    is_postgres = DATABASE_URL.startswith('postgresql://') or DATABASE_URL.startswith('postgres://')
                    
                    if is_postgres:
                        # Get max ID from table
                        result = db.execute(text("SELECT MAX(id) FROM chat_messages"))
                        max_id = result.scalar() or 0
                        # Reset sequence to max_id + 1
                        db.execute(text(f"SELECT setval('chat_messages_id_seq', {max_id + 1}, false)"))
                        db.commit()
                        logger.info(f"Fixed chat_messages sequence. Next ID will be {max_id + 1}")
                        # Retry adding the message
                        db.add(assistant_msg)
                        conversation.updated_at = datetime.utcnow()
                        db.commit()
                    else:
                        # SQLite - recreate the message object
                        assistant_msg = ChatMessage(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=ai_response
                        )
                        db.add(assistant_msg)
                        conversation.updated_at = datetime.utcnow()
                        db.commit()
                except Exception as fix_error:
                    logger.error(f"Failed to fix chat_messages sequence: {fix_error}")
                    raise HTTPException(status_code=500, detail="Database error. Please try again.")
            else:
                raise
        
        logger.info(f"Chat response generated for user {current_user.email}")
        
        return {
            "conversation_id": conversation.id,
            "response": ai_response,
            "message_id": assistant_msg.id
        }
        
    except Exception as e:
        logger.error(f"Error generating chat response: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")


@app.get("/chat/conversations/{chart_id}")
async def list_conversations_endpoint(
    chart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all chat conversations for a specific chart.
    
    SECURITY: Only returns conversations for charts owned by the authenticated user.
    """
    # SECURITY: Verify chart belongs to authenticated user
    chart = db.query(SavedChart).filter(
        SavedChart.id == chart_id,
        SavedChart.user_id == current_user.id  # Critical: ownership check
    ).first()
    
    if not chart:
        raise HTTPException(status_code=404, detail="Chart not found.")
    
    conversations = db.query(ChatConversation).filter(
        ChatConversation.chart_id == chart_id,
        ChatConversation.user_id == current_user.id
    ).order_by(ChatConversation.updated_at.desc()).all()
    
    return [
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "message_count": len(conv.messages)
        }
        for conv in conversations
    ]


@app.get("/chat/conversation/{conversation_id}")
async def get_conversation_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific conversation with all messages."""
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).order_by(ChatMessage.created_at).all()
    
    return {
        "id": conversation.id,
        "title": conversation.title,
        "chart_id": conversation.chart_id,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
    }


@app.post("/api/log-clicks")
@limiter.limit("1000/hour")  # Allow many clicks but prevent abuse
async def log_clicks_endpoint(
    request: Request,
    data: dict
):
    """Log user clicks for debugging purposes."""
    try:
        clicks = data.get('clicks', [])
        page = data.get('page', 'unknown')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # Log each click with detailed information
        logger.info("="*80)
        logger.info("CLICK TRACKING - BATCH RECEIVED")
        logger.info("="*80)
        logger.info(f"Page: {page}")
        logger.info(f"Batch timestamp: {timestamp}")
        logger.info(f"Number of clicks: {len(clicks)}")
        logger.info(f"Client IP: {request.client.host if request.client else 'unknown'}")
        logger.info(f"User Agent: {request.headers.get('user-agent', 'unknown')}")
        logger.info("")
        
        for i, click in enumerate(clicks, 1):
            element = click.get('element', {})
            page_info = click.get('page', {})
            user_info = click.get('user', {})
            viewport = click.get('viewport', {})
            event_info = click.get('event', {})
            
            logger.info(f"--- Click #{i} ---")
            logger.info(f"Timestamp: {click.get('timestamp', 'unknown')}")
            logger.info(f"Page URL: {page_info.get('url', 'unknown')}")
            logger.info(f"Page Title: {page_info.get('title', 'unknown')}")
            logger.info(f"User Logged In: {user_info.get('loggedIn', False)}")
            if user_info.get('email'):
                logger.info(f"User Email: {user_info.get('email')}")
            logger.info(f"Element Tag: {element.get('tag', 'unknown')}")
            if element.get('id'):
                logger.info(f"Element ID: {element.get('id')}")
            if element.get('className'):
                logger.info(f"Element Class: {element.get('className')}")
            if element.get('text'):
                logger.info(f"Element Text: {element.get('text')[:100]}")
            if element.get('href'):
                logger.info(f"Element Href: {element.get('href')}")
            if element.get('type'):
                logger.info(f"Element Type: {element.get('type')}")
            if element.get('name'):
                logger.info(f"Element Name: {element.get('name')}")
            if element.get('value'):
                logger.info(f"Element Value: {element.get('value')}")
            if element.get('dataset'):
                logger.info(f"Element Dataset: {element.get('dataset')}")
            if element.get('ariaLabel'):
                logger.info(f"Element Aria Label: {element.get('ariaLabel')}")
            if element.get('role'):
                logger.info(f"Element Role: {element.get('role')}")
            
            parent = click.get('parent')
            if parent:
                logger.info(f"Parent Tag: {parent.get('tag', 'unknown')}")
                if parent.get('id'):
                    logger.info(f"Parent ID: {parent.get('id')}")
                if parent.get('className'):
                    logger.info(f"Parent Class: {parent.get('className')}")
            
            logger.info(f"Viewport: {viewport.get('width')}x{viewport.get('height')}")
            logger.info(f"Scroll Position: ({viewport.get('scrollX', 0)}, {viewport.get('scrollY', 0)})")
            
            if event_info.get('ctrlKey') or event_info.get('shiftKey') or event_info.get('altKey') or event_info.get('metaKey'):
                modifiers = []
                if event_info.get('ctrlKey'): modifiers.append('Ctrl')
                if event_info.get('shiftKey'): modifiers.append('Shift')
                if event_info.get('altKey'): modifiers.append('Alt')
                if event_info.get('metaKey'): modifiers.append('Meta')
                logger.info(f"Modifier Keys: {', '.join(modifiers)}")
            
            logger.info("")
        
        logger.info("="*80)
        logger.info("CLICK TRACKING - BATCH COMPLETE")
        logger.info("="*80)
        
        return {"status": "logged", "count": len(clicks)}
    
    except Exception as e:
        logger.error(f"Error logging clicks: {e}", exc_info=True)
        # Don't raise - we don't want click logging to break the site
        return {"status": "error", "message": str(e)}


@app.delete("/chat/conversation/{conversation_id}")
async def delete_conversation_endpoint(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chat conversation."""
    conversation = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    
    db.delete(conversation)
    db.commit()
    
    return {"message": "Conversation deleted successfully."}


# ============================================================
# Subscription Management Endpoints
# ============================================================

from subscription import create_subscription_checkout, create_reading_checkout, handle_subscription_webhook
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@app.get("/api/subscription/status")
async def get_subscription_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription status and reading purchase info."""
    # Check for FRIENDS_AND_FAMILY_KEY bypass
    friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
    if not friends_and_family_key:
        # Check headers (case-insensitive)
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "x-friends-and-family-key":
                friends_and_family_key = header_value
                break
    
    # Check if FRIENDS_AND_FAMILY_KEY is valid
    ADMIN_SECRET_KEY = os.getenv("FRIENDS_AND_FAMILY_KEY")
    has_friends_family_access = friends_and_family_key and ADMIN_SECRET_KEY and friends_and_family_key == ADMIN_SECRET_KEY
    
    # All users now have access (Stripe requirements removed)
    # FRIENDS_AND_FAMILY_KEY still tracked for logging
    is_active = True  # Always return True - no payment required
    
    return {
        "has_subscription": is_active,
        "status": "active" if has_friends_family_access else "free_access",
        "start_date": current_user.subscription_start_date.isoformat() if current_user.subscription_start_date else None,
        "end_date": current_user.subscription_end_date.isoformat() if current_user.subscription_end_date else None,
        "has_purchased_reading": current_user.has_purchased_reading or has_friends_family_access,
        "reading_purchase_date": current_user.reading_purchase_date.isoformat() if current_user.reading_purchase_date else None,
        "free_chat_month_end_date": current_user.free_chat_month_end_date.isoformat() if current_user.free_chat_month_end_date else None,
        "is_admin": current_user.is_admin,
        "friends_family_access": has_friends_family_access
    }


@app.post("/api/reading/checkout")
async def create_reading_checkout_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for $28 one-time full reading purchase."""
    try:
        result = create_reading_checkout(
            user_id=current_user.id,
            user_email=current_user.email
        )
        return result
    except Exception as e:
        logger.error(f"Error creating reading checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subscription/checkout")
async def create_subscription_checkout_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for $8/month subscription."""
    try:
        result = create_subscription_checkout(
            user_id=current_user.id,
            user_email=current_user.email
        )
        return result
    except Exception as e:
        logger.error(f"Error creating subscription checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/webhooks/render-deploy")
async def render_deploy_webhook(request: Request):
    """Handle Render deployment webhook to trigger webpage deployment.
    
    This endpoint is called by Render when the API deployment completes.
    It then triggers a deployment of the webpage service using Render's Deploy Hook URL.
    """
    try:
        # Get webpage deploy hook URL from environment
        WEBPAGE_DEPLOY_HOOK_URL = os.getenv("WEBPAGE_DEPLOY_HOOK_URL")
        
        if not WEBPAGE_DEPLOY_HOOK_URL:
            logger.warning("Webpage deploy hook URL not configured. Skipping webpage deployment trigger.")
            return {"status": "skipped", "message": "Webpage deploy hook URL not configured"}
        
        # Trigger webpage deployment using Render's Deploy Hook
        response = requests.post(
            WEBPAGE_DEPLOY_HOOK_URL,
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            logger.info(f"Successfully triggered webpage deployment via deploy hook. Status: {response.status_code}")
            return {
                "status": "success",
                "message": "Webpage deployment triggered",
                "response_status": response.status_code
            }
        else:
            logger.error(f"Failed to trigger webpage deployment. Status: {response.status_code}, Response: {response.text}")
            return {
                "status": "error",
                "message": f"Failed to trigger deployment: {response.status_code}",
                "error": response.text[:500]  # Limit error message length
            }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error triggering webpage deployment: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Network error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Error triggering webpage deployment: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }


@app.post("/api/webhooks/stripe")
async def stripe_webhook_endpoint(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events for subscriptions."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")
    
    try:
        import stripe
        if not STRIPE_WEBHOOK_SECRET:
            raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET not configured")
        
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        
        result = handle_subscription_webhook(event, db)
        return result
    
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
# Famous People Similarity Matching endpoint has been moved to routers/famous_people_routes.py
# The internal function has been moved to services/similarity_service.py
