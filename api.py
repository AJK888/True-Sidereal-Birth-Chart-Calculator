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

# --- Import Chat API Router ---
from chat_api import router as chat_router

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
                "temperature": 0.85,
                "top_p": 0.9,
                "top_k": 40,
                "max_output_tokens": 60000,
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
    """Gemini Call 0 - produce JSON planning blueprint with forensic depth."""
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
        houses_instruction = """For ALL 12 houses, provide a comprehensive analysis. Cover each house in this order:

1st HOUSE (Self & Identity): Physical appearance, first impressions, how you project yourself, vitality, personal identity
2nd HOUSE (Resources & Values): Money, possessions, values, self-worth, material security, what you value
3rd HOUSE (Communication & Learning): Siblings, early education, communication style, local travel, thinking patterns, writing/speaking
4th HOUSE (Home & Roots): Family, home environment, emotional foundations, private life, ancestry, inner security
5th HOUSE (Creativity & Pleasure): Romance, children, creativity, self-expression, hobbies, fun, risk-taking, play
6th HOUSE (Work & Health): Daily work, routines, health, service, pets, habits, duty, practical skills
7th HOUSE (Relationships & Partnerships): Marriage, partnerships, close relationships, contracts, others, projection
8th HOUSE (Transformation & Shared Resources): Death, rebirth, transformation, shared resources, inheritance, taxes, psychology, intimacy
9th HOUSE (Philosophy & Higher Learning): Higher education, philosophy, religion, long-distance travel, publishing, beliefs, expansion of mind
10th HOUSE (Career & Public Standing): Career, reputation, public image, authority, status, life direction, achievements
11th HOUSE (Friends & Aspirations): Friends, groups, hopes, dreams, social causes, technology, innovation, community
12th HOUSE (Spirituality & Unconscious): Subconscious, spirituality, hidden enemies, karma, isolation, secrets, transcendence

For each house, provide COMPREHENSIVE analysis covering:

1. HOUSE CUSP & RULER:
   - The sign on the cusp (both sidereal and tropical - note if they differ)
   - The ruling planet(s) for that sign
   - Where the ruling planet is located (sign, house, degree) in BOTH sidereal and tropical systems
   - The condition of the ruler (dignified, debilitated, retrograde, etc.) in both systems

2. ALL PLANETS IN THE HOUSE:
   - List EVERY planet that falls in this house in the SIDEREAL system (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Chiron, Nodes, etc.)
   - List EVERY planet that falls in this house in the TROPICAL system
   - For each planet, note: its sign, degree, house position, aspects, retrograde status
   - Compare sidereal vs tropical placements - note where planets appear in different houses between systems and what that means

3. ALL ZODIAC SIGNS IN THE HOUSE:
   - Identify ALL signs that appear within this house (houses can span multiple signs)
   - Note the degree ranges for each sign within the house
   - Explain how each sign's energy influences this life domain
   - Compare sidereal vs tropical sign distributions in the house

4. SYNTHESIS:
   - Show how the domain is "engineered" by multiple factors converging (house ruler + ALL planets in house + sign distributions + aspects to cusp)
   - Explain how sidereal placements reveal the SOUL-LEVEL approach to this domain
   - Explain how tropical placements reveal the PERSONALITY-LEVEL approach to this domain
   - Note any contradictions or tensions between sidereal and tropical placements
   - Give concrete examples of how this shows up in real life
   - Connect to numerology where relevant
   - Note if the house is empty (no planets) and what that means - but still analyze the ruler and sign distributions

5. STELLIUMS & CONCENTRATIONS:
   - If 3+ planets are in this house, analyze the stellium energy and how it concentrates focus in this domain
   - Note if the stellium appears in sidereal, tropical, or both systems

Be thorough - examine every planet, every sign, and both systems for each of the 12 houses."""
    
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

This section should be SUBSTANTIAL and well-formatted. Each aspect gets its own clearly separated subsection.

FORMAT FOR EACH ASPECT (cover AT LEAST 10 major aspects):

[PLANET 1] [ASPECT TYPE] [PLANET 2] ([orb]°)

Core Dynamic: [1-2 sentences naming the fundamental tension or gift this creates]

Why This Matters: [3-4 sentences explaining the psychological mechanism. What does this aspect create internally? How does it shape their default responses? Reference both sidereal and tropical contexts if relevant.]

How It Shows Up:
- In relationships: [specific example]
- At work: [specific example]  
- Internally: [what they experience in their own mind/emotions]

The Growth Edge: [2-3 sentences on what shifts when they work with this consciously. What's the integrated expression vs the reactive pattern?]

---

[Leave a blank line and "---" separator between each aspect for readability]

AFTER ALL ASPECTS, ADD A SECTION ON PATTERNS:

ASPECT PATTERNS IN YOUR CHART

For each pattern (Grand Trines, T-Squares, Stelliums, Yods, Kites, Grand Crosses):

[PATTERN NAME]: [Planets involved]

What This Geometry Creates: [3-4 sentences explaining the psychological function—how does this shape concentrate or distribute energy?]

The Life Theme: [2-3 sentences connecting to earlier themes in the reading]

Real-Life Expression: [Concrete example of how this pattern shows up in their daily life or major life decisions]

SHADOW, CONTRADICTIONS & GROWTH EDGES

FORMAT THIS SECTION WITH CLEAR SUBSECTIONS:

For each shadow pattern, use this structure:

SHADOW: [Name of the Shadow Pattern]

The Pattern: [2-3 sentences describing what this looks like in behavior]

The Driver: [2-3 sentences explaining WHY this pattern exists - what chart factors create it]

The Cost: [1-2 sentences on what this costs them in life/relationships]

The Integration: [2-3 sentences with a concrete "pattern interrupt" - what they can DO differently]

---

[Use "---" between each shadow pattern for visual separation]

Cover at least 3 shadow patterns from blueprint.shadow_contradictions.

GROWTH EDGES

After the shadow patterns, add a section called "Growth Edges" with actionable experiments:

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
    """Gemini Call 3 - polish entire reading for forensic coherence."""
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
    
    return await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=65000,
        temperature=0.4,
        call_label="G3_polish_full_reading"
    )


async def g4_famous_people_section(
    llm: Gemini3Client,
    serialized_chart: dict,
    chart_summary: str,
    famous_people_matches: list,
    unknown_time: bool
) -> str:
    """Gemini Call 4 - Generate famous people comparison section."""
    logger.info("="*60)
    logger.info("G4: Generating Famous People Section")
    logger.info(f"Number of matches: {len(famous_people_matches)}")
    logger.info("="*60)
    
    # Format famous people data for the LLM
    famous_people_data = []
    for match in famous_people_matches[:10]:  # Limit to top 10
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

Your task is to explain:
1. WHAT chart similarities they share (specific planetary placements, aspects, numerology, etc.)
2. WHAT personal/psychological similarities these chart patterns suggest

Be specific and forensic:
- Name exact chart factors that match (e.g., "Both have Sun in Aries (Sidereal) and Moon in Scorpio (Tropical)")
- Explain what these shared patterns mean psychologically
- Connect chart similarities to observable traits or life patterns
- Be insightful, not generic

Tone: Clinical precision with warm delivery. Second person ("you share...", "like [famous person], you...")."""
    
    user_prompt = f"""**User's Chart Summary:**
{chart_summary}

**Famous People Matches:**
{famous_people_json}

**Instructions:**
Write a section titled "Famous People & Chart Similarities" that:

1. Introduces the concept: Explain that sharing chart patterns with notable figures can reveal archetypal energies and life themes.

2. For each famous person (focus on top 3-5 highest scoring matches):
   - Name the person and their occupation/notability
   - List the SPECIFIC chart similarities (use the matching_factors list)
   - Explain what these shared patterns suggest about:
     * Psychological traits
     * Life themes or archetypal energies
     * Potential strengths or challenges
   - Be specific: "You share [X planet] in [Y sign] (Sidereal), which suggests [psychological trait]. Like [famous person], this manifests as [concrete example]."

3. Synthesis: End with a paragraph that synthesizes what these collective similarities reveal about the user's archetypal patterns and potential life themes.

**Important:**
- Use the matching_factors to be precise about what matches
- Don't just list similarities—explain what they MEAN
- Connect chart patterns to psychological/life patterns
- Be insightful, not generic
- Focus on the highest scoring matches (similarity_score)
- If birth time is unknown, don't mention house placements

Write in second person. No markdown, bold, or decorative separators."""
    
    return await llm.generate(
        system=system_prompt,
        user=user_prompt,
        max_output_tokens=4000,
        temperature=0.7,
        call_label="G4_famous_people_section"
    )


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
            max_output_tokens=2000,  # Increased for more comprehensive reading
            temperature=0.7,  # Higher for more creative and nuanced responses
            call_label="snapshot_reading"
        )
        
        return response.strip()
        
    except Exception as e:
        logger.error(f"Error generating snapshot reading: {e}", exc_info=True)
        return "Snapshot reading is temporarily unavailable."


async def get_gemini3_reading(chart_data: dict, unknown_time: bool, db: Session = None) -> str:
    """Four-call Gemini 3 pipeline with optional famous people section."""
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
        
        # Generate famous people section if database session is available
        famous_people_section = ""
        if db:
            try:
                famous_people_matches = await find_similar_famous_people_internal(chart_data, limit=10, db=db)
                if famous_people_matches and len(famous_people_matches.get('matches', [])) > 0:
                    logger.info(f"Found {len(famous_people_matches['matches'])} famous people matches, generating section...")
                    famous_people_section = await g4_famous_people_section(
                        llm, serialized_chart, chart_summary, famous_people_matches['matches'], unknown_time
                    )
                    final_reading = f"{final_reading}\n\n{famous_people_section}"
            except Exception as e:
                logger.warning(f"Could not generate famous people section: {e}", exc_info=True)
                # Continue without famous people section
        
        final_reading = sanitize_reading_text(final_reading).strip()
        
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
            # Get database session for famous people matching
            from database import SessionLocal
            db = SessionLocal()
            try:
                reading_text = await get_gemini3_reading(chart_data, unknown_time, db=db)
            finally:
                db.close()
            logger.info(f"AI Reading successfully generated for: {chart_name} (length: {len(reading_text)} characters)")
            
            # Store reading in cache for frontend retrieval
            chart_hash = generate_chart_hash(chart_data, unknown_time)
            reading_cache[chart_hash] = {
                'reading': reading_text,
                'timestamp': datetime.now(),
                'chart_name': chart_name
            }
            logger.info(f"Reading stored in cache with hash: {chart_hash}")
            
            # Also save reading to user's saved chart if user exists
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
                            
                            for chart in saved_charts:
                                if chart.chart_data_json:
                                    try:
                                        saved_chart_data = json.loads(chart.chart_data_json)
                                        saved_chart_hash = generate_chart_hash(saved_chart_data, chart.unknown_time)
                                        if saved_chart_hash == chart_hash:
                                            chart.ai_reading = reading_text
                                            db.commit()
                                            logger.info(f"Reading saved to chart ID {chart.id} for user {user_email}")
                                            break
                                    except Exception as e:
                                        logger.warning(f"Error checking chart hash: {e}")
                                        continue
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
                if snapshot_reading and snapshot_reading != "Snapshot reading is temporarily unavailable." and data.user_email:
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
                        
                        # Send to user
                        send_snapshot_email_via_sendgrid(
                            snapshot_reading,
                            data.user_email,
                            data.full_name,
                            birth_date_str,
                            birth_time_str,
                            data.location
                        )
                        
                        # Send to admin
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
                    
                    # Prepare user inputs for reading generation
                    user_inputs = {
                        'full_name': data.full_name,
                        'user_email': data.user_email
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
@limiter.limit("100/hour")
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


async def get_gemini_chat_response(chart_data: dict, reading: Optional[str], conversation_history: List[dict], user_message: str, chart_name: str = "User") -> str:
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
    
    user_prompt = f"""=== CHART OWNER ===
You are speaking directly with the chart owner about THEIR chart. All data below belongs to them.

=== CHART DATA ===
{chart_summary}
{reading_context}
{conversation_context}

=== USER'S CURRENT QUESTION ===
{user_message}

=== INSTRUCTIONS ===
Provide a helpful, personalized response that:
1. Addresses their specific question
2. References their chart placements and aspects when relevant
3. Quotes or paraphrases relevant parts of their reading if it applies to their question
4. Offers practical, actionable insights based on their unique astrological blueprint
5. Speaks directly to them as the owner of this chart"""
    
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
    db.commit()
    
    # Parse chart data
    chart_data = json.loads(chart.chart_data_json) if chart.chart_data_json else {}
    
    try:
        # Get AI response - passing verified user's chart data
        # Security: chart ownership already verified above (user_id check)
        ai_response = await get_gemini_chat_response(
            chart_data=chart_data,
            reading=chart.ai_reading,
            conversation_history=conversation_history,
            user_message=data.message,
            chart_name=chart.chart_name
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
        db.commit()
        
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


# ============================================================================
# Famous People Similarity Matching (Free Feature)
# ============================================================================

def extract_stelliums(chart_data: dict) -> dict:
    """
    Extract stelliums from chart data (both sidereal and tropical).
    Returns dict with 'sidereal' and 'tropical' lists of stellium descriptions.
    """
    stelliums = {"sidereal": [], "tropical": []}
    
    # Extract from aspect patterns
    s_patterns = chart_data.get('sidereal_aspect_patterns', [])
    t_patterns = chart_data.get('tropical_aspect_patterns', [])
    
    for pattern in s_patterns:
        desc = pattern.get('description', '')
        if 'stellium' in desc.lower():
            stelliums['sidereal'].append(desc)
    
    for pattern in t_patterns:
        desc = pattern.get('description', '')
        if 'stellium' in desc.lower():
            stelliums['tropical'].append(desc)
    
    return stelliums


def extract_top_aspects_from_chart(chart_data: dict, top_n: int = 3) -> dict:
    """
    Extract top N aspects from chart data (both sidereal and tropical).
    Returns dict with 'sidereal' and 'tropical' lists of aspect dicts.
    """
    aspects = {"sidereal": [], "tropical": []}
    
    # Get sidereal aspects
    sidereal_aspects = chart_data.get('sidereal_aspects', [])
    sorted_sidereal = sorted(
        sidereal_aspects,
        key=lambda a: (
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").isdigit() else 0,
            abs(float(str(a.get("orb", "999")).replace("°", "").strip()) if isinstance(a.get("orb"), str) else float(a.get("orb", 999)))
        )
    )[:top_n]
    
    for aspect in sorted_sidereal:
        p1_name = aspect.get("p1_name", "").split(" in ")[0].strip()
        p2_name = aspect.get("p2_name", "").split(" in ")[0].strip()
        aspects["sidereal"].append({
            "p1": p1_name,
            "p2": p2_name,
            "type": aspect.get("type", ""),
        })
    
    # Get tropical aspects
    tropical_aspects = chart_data.get('tropical_aspects', [])
    sorted_tropical = sorted(
        tropical_aspects,
        key=lambda a: (
            -float(a.get("score", 0)) if isinstance(a.get("score"), (int, float, str)) and str(a.get("score")).replace(".", "").isdigit() else 0,
            abs(float(str(a.get("orb", "999")).replace("°", "").strip()) if isinstance(a.get("orb"), str) else float(a.get("orb", 999)))
        )
    )[:top_n]
    
    for aspect in sorted_tropical:
        p1_name = aspect.get("p1_name", "").split(" in ")[0].strip()
        p2_name = aspect.get("p2_name", "").split(" in ")[0].strip()
        aspects["tropical"].append({
            "p1": p1_name,
            "p2": p2_name,
            "type": aspect.get("type", ""),
        })
    
    return aspects


def normalize_master_number(num_str):
    """Normalize master numbers (e.g., '33/6' -> ['33', '6'])"""
    if not num_str:
        return []
    num_str = str(num_str)
    if '/' in num_str:
        return [num_str.split('/')[0], num_str.split('/')[-1]]
    return [num_str]


def check_strict_matches(user_chart_data: dict, famous_person: FamousPerson, user_numerology: dict, user_chinese_zodiac: dict) -> tuple[bool, list[str]]:
    """
    Check if famous person matches strict criteria:
    1. Sun AND Moon in sidereal
    2. Sun AND Moon in tropical
    3. Numerology day AND life path number
    4. Chinese zodiac AND (numerology day OR life path number)
    
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    matches = []
    
    # Extract user's signs
    s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', [])}
    t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', [])}
    
    def extract_sign(position_str):
        if not position_str:
            return None
        parts = position_str.split()
        return parts[-1] if parts else None
    
    user_sun_s = extract_sign(s_positions.get('Sun', {}).get('position')) if 'Sun' in s_positions else None
    user_moon_s = extract_sign(s_positions.get('Moon', {}).get('position')) if 'Moon' in s_positions else None
    user_sun_t = extract_sign(t_positions.get('Sun', {}).get('position')) if 'Sun' in t_positions else None
    user_moon_t = extract_sign(t_positions.get('Moon', {}).get('position')) if 'Moon' in t_positions else None
    
    # 1. Check Sun AND Moon in sidereal
    if user_sun_s and user_moon_s and famous_person.sun_sign_sidereal and famous_person.moon_sign_sidereal:
        if user_sun_s == famous_person.sun_sign_sidereal and user_moon_s == famous_person.moon_sign_sidereal:
            matches.append("strict_sun_moon_sidereal")
            reasons.append(f"Matching Sun ({user_sun_s}) and Moon ({user_moon_s}) in Sidereal")
    
    # 2. Check Sun AND Moon in tropical
    if user_sun_t and user_moon_t and famous_person.sun_sign_tropical and famous_person.moon_sign_tropical:
        if user_sun_t == famous_person.sun_sign_tropical and user_moon_t == famous_person.moon_sign_tropical:
            matches.append("strict_sun_moon_tropical")
            reasons.append(f"Matching Sun ({user_sun_t}) and Moon ({user_moon_t}) in Tropical")
    
    # 3. Check numerology day AND life path number
    user_day = user_numerology.get('day_number') if isinstance(user_numerology, dict) else None
    user_life_path = user_numerology.get('life_path_number') if isinstance(user_numerology, dict) else None
    
    if user_day and user_life_path and famous_person.day_number and famous_person.life_path_number:
        user_day_norm = normalize_master_number(user_day)
        fp_day_norm = normalize_master_number(famous_person.day_number)
        user_lp_norm = normalize_master_number(user_life_path)
        fp_lp_norm = normalize_master_number(famous_person.life_path_number)
        
        day_match = any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm)
        lp_match = any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm)
        
        if day_match and lp_match:
            matches.append("strict_numerology")
            reasons.append(f"Matching Day Number ({user_day}) and Life Path Number ({user_life_path})")
    
    # 4. Check Chinese zodiac AND (numerology day OR life path number)
    user_chinese = user_chinese_zodiac.get('animal') if isinstance(user_chinese_zodiac, dict) else None
    if user_chinese and famous_person.chinese_zodiac_animal:
        if user_chinese.lower() == famous_person.chinese_zodiac_animal.lower():
            # Check if also matches numerology day
            if user_day and famous_person.day_number:
                user_day_norm = normalize_master_number(user_day)
                fp_day_norm = normalize_master_number(famous_person.day_number)
                if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                    matches.append("strict_chinese_day")
                    reasons.append(f"Matching Chinese Zodiac ({user_chinese}) and Day Number ({user_day})")
            
            # Check if also matches life path number
            if user_life_path and famous_person.life_path_number:
                user_lp_norm = normalize_master_number(user_life_path)
                fp_lp_norm = normalize_master_number(famous_person.life_path_number)
                if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                    matches.append("strict_chinese_lifepath")
                    reasons.append(f"Matching Chinese Zodiac ({user_chinese}) and Life Path Number ({user_life_path})")
    
    return len(matches) > 0, reasons


def check_aspect_matches(user_chart_data: dict, famous_person: FamousPerson) -> tuple[bool, list[str]]:
    """
    Check if famous person shares 2 of the top 3 aspects.
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    
    # Get user's top 3 aspects
    user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=3)
    
    # Get famous person's top 3 aspects
    if not famous_person.top_aspects_json:
        return False, []
    
    try:
        fp_aspects = json.loads(famous_person.top_aspects_json)
    except:
        return False, []
    
    # Compare sidereal aspects
    user_s_aspects = user_aspects.get('sidereal', [])
    fp_s_aspects = fp_aspects.get('sidereal', [])
    
    s_matches = 0
    matched_aspects_s = []
    for u_aspect in user_s_aspects:
        for fp_aspect in fp_s_aspects:
            # Check if same planets and same aspect type (order doesn't matter)
            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                s_matches += 1
                matched_aspects_s.append(f"{u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                break
    
    # Compare tropical aspects
    user_t_aspects = user_aspects.get('tropical', [])
    fp_t_aspects = fp_aspects.get('tropical', [])
    
    t_matches = 0
    matched_aspects_t = []
    for u_aspect in user_t_aspects:
        for fp_aspect in fp_t_aspects:
            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                t_matches += 1
                matched_aspects_t.append(f"{u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                break
    
    # Need at least 2 matches total (can be from either system)
    total_matches = s_matches + t_matches
    
    if total_matches >= 2:
        if matched_aspects_s:
            reasons.append(f"Sharing {s_matches} top aspect(s) in Sidereal: {', '.join(matched_aspects_s)}")
        if matched_aspects_t:
            reasons.append(f"Sharing {t_matches} top aspect(s) in Tropical: {', '.join(matched_aspects_t)}")
        return True, reasons
    
    return False, []


def check_stellium_matches(user_chart_data: dict, famous_person: FamousPerson) -> tuple[bool, list[str]]:
    """
    Check if famous person has the same stelliums.
    Returns: (is_match, list of match reasons)
    """
    reasons = []
    
    # Get user's stelliums
    user_stelliums = extract_stelliums(user_chart_data)
    
    # Get famous person's stelliums
    if not famous_person.chart_data_json:
        return False, []
    
    try:
        fp_chart = json.loads(famous_person.chart_data_json)
        fp_stelliums = extract_stelliums(fp_chart)
    except:
        return False, []
    
    # Compare stelliums (extract sign/house from description)
    def extract_stellium_key(desc):
        """Extract key info from stellium description"""
        # Format: "4 bodies in Aquarius (Air, Fixed Sign Stellium)" or "3 bodies in House 5 (House Stellium)"
        if 'Sign Stellium' in desc:
            # Extract sign name
            parts = desc.split(' bodies in ')
            if len(parts) > 1:
                sign = parts[1].split(' (')[0].strip()
                return ('sign', sign)
        elif 'House Stellium' in desc:
            # Extract house number
            parts = desc.split('House ')
            if len(parts) > 1:
                house = parts[1].split(' (')[0].strip()
                return ('house', house)
        return None
    
    matched_stelliums = []
    
    # Compare sidereal stelliums
    for u_stellium in user_stelliums.get('sidereal', []):
        u_key = extract_stellium_key(u_stellium)
        if u_key:
            for fp_stellium in fp_stelliums.get('sidereal', []):
                fp_key = extract_stellium_key(fp_stellium)
                if u_key == fp_key:
                    matched_stelliums.append(f"Sidereal: {u_stellium}")
                    break
    
    # Compare tropical stelliums
    for u_stellium in user_stelliums.get('tropical', []):
        u_key = extract_stellium_key(u_stellium)
        if u_key:
            for fp_stellium in fp_stelliums.get('tropical', []):
                fp_key = extract_stellium_key(fp_stellium)
                if u_key == fp_key:
                    matched_stelliums.append(f"Tropical: {u_stellium}")
                    break
    
    if matched_stelliums:
        reasons.extend([f"Shared stellium: {s}" for s in matched_stelliums])
        return True, reasons
    
    return False, []


def calculate_comprehensive_similarity_score(user_chart_data: dict, famous_person: FamousPerson) -> float:
    """
    Calculate comprehensive similarity score including all placements and aspects.
    Returns a score from 0-100.
    """
    try:
        # Load famous person's chart data
        if not famous_person.chart_data_json:
            return 0.0
        
        fp_chart = json.loads(famous_person.chart_data_json)
        fp_planetary_placements = {}
        if famous_person.planetary_placements_json:
            try:
                fp_planetary_placements = json.loads(famous_person.planetary_placements_json)
            except:
                pass
        
        score = 0.0
        max_possible_score = 0.0
        
        # Extract user's positions
        s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', [])}
        t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', [])}
        s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', [])}
        t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', [])}
        
        # Helper function to extract sign from position string
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        # ========================================================================
        # PLANETARY PLACEMENTS (Sidereal & Tropical) - All planets
        # ========================================================================
        
        # All planets to compare (weighted by importance)
        planets_to_compare = [
            ('Sun', 5.0),
            ('Moon', 5.0),
            ('Mercury', 3.0),
            ('Venus', 3.0),
            ('Mars', 3.0),
            ('Jupiter', 3.0),
            ('Saturn', 3.0),
            ('Uranus', 3.0),
            ('Neptune', 3.0),
            ('Pluto', 3.0),
        ]
        
        for planet_name, weight in planets_to_compare:
            # Sidereal comparison
            user_planet_s = None
            fp_planet_s = None
            
            if planet_name in s_positions:
                user_planet_s = extract_sign(s_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if fp_planetary_placements.get('sidereal', {}).get(planet_name):
                fp_planet_s = fp_planetary_placements['sidereal'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_sidereal:
                fp_planet_s = famous_person.sun_sign_sidereal
            elif planet_name == 'Moon' and famous_person.moon_sign_sidereal:
                fp_planet_s = famous_person.moon_sign_sidereal
            # Fallback to chart_data_json
            elif fp_chart.get('sidereal_major_positions'):
                for p in fp_chart['sidereal_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_s = extract_sign(p.get('position'))
                        break
            
            if user_planet_s and fp_planet_s:
                max_possible_score += weight
                if user_planet_s == fp_planet_s:
                    score += weight
            
            # Tropical comparison
            user_planet_t = None
            fp_planet_t = None
            
            if planet_name in t_positions:
                user_planet_t = extract_sign(t_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if fp_planetary_placements.get('tropical', {}).get(planet_name):
                fp_planet_t = fp_planetary_placements['tropical'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_tropical:
                fp_planet_t = famous_person.sun_sign_tropical
            elif planet_name == 'Moon' and famous_person.moon_sign_tropical:
                fp_planet_t = famous_person.moon_sign_tropical
            # Fallback to chart_data_json
            elif fp_chart.get('tropical_major_positions'):
                for p in fp_chart['tropical_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_t = extract_sign(p.get('position'))
                        break
            
            if user_planet_t and fp_planet_t:
                max_possible_score += weight
                if user_planet_t == fp_planet_t:
                    score += weight
        
        # Rising/Ascendant signs (if birth time known) - weight: 5 points each system
        if not user_chart_data.get('unknown_time'):
            user_rising_s = None
            user_rising_t = None
            fp_rising_s = None
            fp_rising_t = None
            
            if 'Ascendant' in s_extra:
                asc_info = s_extra['Ascendant'].get('info', '')
                user_rising_s = asc_info.split()[0] if asc_info else None
            
            if 'Ascendant' in t_extra:
                asc_info = t_extra['Ascendant'].get('info', '')
                user_rising_t = asc_info.split()[0] if asc_info else None
            
            # Get from famous person (if they have birth time)
            if not famous_person.unknown_time and fp_chart.get('sidereal_additional_points'):
                for p in fp_chart['sidereal_additional_points']:
                    if p.get('name') == 'Ascendant':
                        asc_info = p.get('info', '')
                        fp_rising_s = asc_info.split()[0] if asc_info else None
                        break
            
            if not famous_person.unknown_time and fp_chart.get('tropical_additional_points'):
                for p in fp_chart['tropical_additional_points']:
                    if p.get('name') == 'Ascendant':
                        asc_info = p.get('info', '')
                        fp_rising_t = asc_info.split()[0] if asc_info else None
                        break
            
            if user_rising_s and fp_rising_s:
                max_possible_score += 5.0
                if user_rising_s == fp_rising_s:
                    score += 5.0
            
            if user_rising_t and fp_rising_t:
                max_possible_score += 5.0
                if user_rising_t == fp_rising_t:
                    score += 5.0
        
        # ========================================================================
        # ASPECTS (Top 3 from both systems)
        # ========================================================================
        # If at least 2 out of 3 top aspects match, award 10 points
        
        user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=3)
        
        if famous_person.top_aspects_json:
            try:
                fp_aspects = json.loads(famous_person.top_aspects_json)
                
                # Count matching aspects in sidereal
                sidereal_matches = 0
                user_s_aspects = user_aspects.get('sidereal', [])
                fp_s_aspects = fp_aspects.get('sidereal', [])
                
                for u_aspect in user_s_aspects:
                    for fp_aspect in fp_s_aspects:
                        u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                        fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                        if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                            sidereal_matches += 1
                            break
                
                # Count matching aspects in tropical
                tropical_matches = 0
                user_t_aspects = user_aspects.get('tropical', [])
                fp_t_aspects = fp_aspects.get('tropical', [])
                
                for u_aspect in user_t_aspects:
                    for fp_aspect in fp_t_aspects:
                        u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                        fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                        if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                            tropical_matches += 1
                            break
                
                # Award 10 points if at least 2 out of 3 aspects match in either system
                if sidereal_matches >= 2 or tropical_matches >= 2:
                    max_possible_score += 10.0
                    score += 10.0
            except:
                pass
        
        # ========================================================================
        # NUMEROLOGY
        # ========================================================================
        
        # Life Path Number - weight: 10 points
        user_life_path = user_chart_data.get('numerology', {}).get('life_path_number')
        fp_life_path = famous_person.life_path_number
        
        if user_life_path and fp_life_path:
            max_possible_score += 10.0
            user_lp_norm = normalize_master_number(user_life_path)
            fp_lp_norm = normalize_master_number(fp_life_path)
            
            if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                score += 10.0
        
        # Day Number - weight: 10 points
        user_day_num = user_chart_data.get('numerology', {}).get('day_number')
        fp_day_num = famous_person.day_number
        
        if user_day_num and fp_day_num:
            max_possible_score += 10.0
            user_day_norm = normalize_master_number(user_day_num)
            fp_day_norm = normalize_master_number(fp_day_num)
            
            if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                score += 10.0
        
        # ========================================================================
        # CHINESE ZODIAC
        # ========================================================================
        
        # Chinese Zodiac Animal - weight: 10 points
        user_chinese_animal = user_chart_data.get('chinese_zodiac', {}).get('animal')
        fp_chinese_animal = famous_person.chinese_zodiac_animal
        
        if user_chinese_animal and fp_chinese_animal:
            max_possible_score += 10.0
            if user_chinese_animal.lower() == fp_chinese_animal.lower():
                score += 10.0
        
        # ========================================================================
        # DOMINANT ELEMENT - Not included in scoring (only shown in matching_factors for display)
        # ========================================================================
        # Dominant Element is still extracted and shown in matching_factors list,
        # but it is NOT included in the score calculation per user requirements
        
        # ========================================================================
        # CALCULATE FINAL SCORE
        # ========================================================================
        
        # Normalize to 0-100 scale based on maximum possible score
        if max_possible_score > 0:
            normalized_score = (score / max_possible_score) * 100.0
        else:
            # If max_possible_score is 0, it means no planetary placements were found to compare
            # This could happen if chart data structure is unexpected
            # Log this for debugging
            logger.warning(
                f"max_possible_score is 0 for {famous_person.name if famous_person else 'unknown'}. "
                f"Score: {score}, "
                f"User has sidereal: {bool(user_chart_data.get('sidereal_major_positions'))}, "
                f"User has tropical: {bool(user_chart_data.get('tropical_major_positions'))}, "
                f"FP has placements: {bool(fp_planetary_placements)}, "
                f"FP has chart: {bool(fp_chart)}"
            )
            # If we have matches (strict/aspect/stellium), give a minimum score
            # Otherwise return 0
            normalized_score = 0.0
        
        result = min(normalized_score, 100.0)
        return result
    
    except Exception as e:
        logger.error(f"Error calculating comprehensive similarity: {e}", exc_info=True)
        return 0.0


def calculate_chart_similarity(user_chart_data: dict, famous_person: FamousPerson) -> float:
    """
    Calculate comprehensive similarity score between user chart and famous person chart.
    Considers ALL factors: planetary placements (sidereal/tropical), numerology, Chinese zodiac.
    Returns a score from 0-100. The more factors that match, the higher the score.
    """
    try:
        # Load famous person's chart data
        if not famous_person.chart_data_json:
            return 0.0
        
        fp_chart = json.loads(famous_person.chart_data_json)
        fp_planetary_placements = {}
        if famous_person.planetary_placements_json:
            try:
                fp_planetary_placements = json.loads(famous_person.planetary_placements_json)
            except:
                pass
        
        score = 0.0
        max_possible_score = 0.0
        
        # Extract user's positions
        s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', [])}
        t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', [])}
        s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', [])}
        t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', [])}
        
        # Helper function to extract sign from position string
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        # ========================================================================
        # PLANETARY PLACEMENTS (Sidereal & Tropical)
        # ========================================================================
        
        # Major planets to compare (weighted by importance)
        planets_to_compare = [
            ('Sun', 8.0),      # Most important - 8 points each system = 16 total
            ('Moon', 8.0),     # Most important - 8 points each system = 16 total
            ('Mercury', 3.0),  # 3 points each system = 6 total
            ('Venus', 3.0),    # 3 points each system = 6 total
            ('Mars', 3.0),     # 3 points each system = 6 total
            ('Jupiter', 2.0), # 2 points each system = 4 total
            ('Saturn', 2.0),   # 2 points each system = 4 total
        ]
        
        for planet_name, weight in planets_to_compare:
            # Sidereal comparison
            user_planet_s = None
            fp_planet_s = None
            
            if planet_name in s_positions:
                user_planet_s = extract_sign(s_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if fp_planetary_placements.get('sidereal', {}).get(planet_name):
                fp_planet_s = fp_planetary_placements['sidereal'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_sidereal:
                fp_planet_s = famous_person.sun_sign_sidereal
            elif planet_name == 'Moon' and famous_person.moon_sign_sidereal:
                fp_planet_s = famous_person.moon_sign_sidereal
            # Fallback to chart_data_json
            elif fp_chart.get('sidereal_major_positions'):
                for p in fp_chart['sidereal_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_s = extract_sign(p.get('position'))
                        break
            
            if user_planet_s and fp_planet_s:
                max_possible_score += weight
                if user_planet_s == fp_planet_s:
                    score += weight
            
            # Tropical comparison
            user_planet_t = None
            fp_planet_t = None
            
            if planet_name in t_positions:
                user_planet_t = extract_sign(t_positions[planet_name].get('position'))
            
            # Try to get from famous person's stored placements
            if fp_planetary_placements.get('tropical', {}).get(planet_name):
                fp_planet_t = fp_planetary_placements['tropical'][planet_name].get('sign')
            # Fallback to database columns (for Sun/Moon which are indexed)
            elif planet_name == 'Sun' and famous_person.sun_sign_tropical:
                fp_planet_t = famous_person.sun_sign_tropical
            elif planet_name == 'Moon' and famous_person.moon_sign_tropical:
                fp_planet_t = famous_person.moon_sign_tropical
            # Fallback to chart_data_json
            elif fp_chart.get('tropical_major_positions'):
                for p in fp_chart['tropical_major_positions']:
                    if p.get('name') == planet_name:
                        fp_planet_t = extract_sign(p.get('position'))
                        break
            
            if user_planet_t and fp_planet_t:
                max_possible_score += weight
                if user_planet_t == fp_planet_t:
                    score += weight
        
        # Rising/Ascendant signs (if birth time known) - weight: 4 points each system
        if not user_chart_data.get('unknown_time'):
            user_rising_s = None
            user_rising_t = None
            fp_rising_s = None
            fp_rising_t = None
            
            if 'Ascendant' in s_extra:
                asc_info = s_extra['Ascendant'].get('info', '')
                user_rising_s = asc_info.split()[0] if asc_info else None
            
            if 'Ascendant' in t_extra:
                asc_info = t_extra['Ascendant'].get('info', '')
                user_rising_t = asc_info.split()[0] if asc_info else None
            
            # Get from famous person (if they have birth time)
            if not famous_person.unknown_time and fp_chart.get('sidereal_additional_points'):
                for p in fp_chart['sidereal_additional_points']:
                    if p.get('name') == 'Ascendant':
                        asc_info = p.get('info', '')
                        fp_rising_s = asc_info.split()[0] if asc_info else None
                        break
            
            if not famous_person.unknown_time and fp_chart.get('tropical_additional_points'):
                for p in fp_chart['tropical_additional_points']:
                    if p.get('name') == 'Ascendant':
                        asc_info = p.get('info', '')
                        fp_rising_t = asc_info.split()[0] if asc_info else None
                        break
            
            if user_rising_s and fp_rising_s:
                max_possible_score += 4.0
                if user_rising_s == fp_rising_s:
                    score += 4.0
            
            if user_rising_t and fp_rising_t:
                max_possible_score += 4.0
                if user_rising_t == fp_rising_t:
                    score += 4.0
        
        # ========================================================================
        # NUMEROLOGY
        # ========================================================================
        
        # Life Path Number - weight: 5 points
        user_life_path = user_chart_data.get('numerology', {}).get('life_path_number')
        fp_life_path = famous_person.life_path_number
        
        if user_life_path and fp_life_path:
            max_possible_score += 5.0
            # Handle master numbers (e.g., "33/6" matches "33/6" or "6")
            user_lp_clean = str(user_life_path).split('/')[0] if '/' in str(user_life_path) else str(user_life_path)
            fp_lp_clean = str(fp_life_path).split('/')[0] if '/' in str(fp_life_path) else str(fp_life_path)
            
            if user_lp_clean == fp_lp_clean:
                score += 5.0
            # Also check if reduced forms match (e.g., "33/6" matches "6")
            elif '/' in str(user_life_path) and str(user_life_path).split('/')[-1] == fp_lp_clean:
                score += 3.0  # Partial match
            elif '/' in str(fp_life_path) and str(fp_life_path).split('/')[-1] == user_lp_clean:
                score += 3.0  # Partial match
        
        # Day Number - weight: 3 points
        user_day_num = user_chart_data.get('numerology', {}).get('day_number')
        fp_day_num = famous_person.day_number
        
        if user_day_num and fp_day_num:
            max_possible_score += 3.0
            # Handle master numbers
            user_day_clean = str(user_day_num).split('/')[0] if '/' in str(user_day_num) else str(user_day_num)
            fp_day_clean = str(fp_day_num).split('/')[0] if '/' in str(fp_day_num) else str(fp_day_num)
            
            if user_day_clean == fp_day_clean:
                score += 3.0
            elif '/' in str(user_day_num) and str(user_day_num).split('/')[-1] == fp_day_clean:
                score += 2.0  # Partial match
            elif '/' in str(fp_day_num) and str(fp_day_num).split('/')[-1] == user_day_clean:
                score += 2.0  # Partial match
        
        # ========================================================================
        # CHINESE ZODIAC
        # ========================================================================
        
        # Chinese Zodiac Animal - weight: 4 points
        user_chinese_animal = user_chart_data.get('chinese_zodiac', {}).get('animal')
        fp_chinese_animal = famous_person.chinese_zodiac_animal
        
        if user_chinese_animal and fp_chinese_animal:
            max_possible_score += 4.0
            if user_chinese_animal.lower() == fp_chinese_animal.lower():
                score += 4.0
        
        # ========================================================================
        # DOMINANT ELEMENT
        # ========================================================================
        
        # Dominant Element - Sidereal (weight: 2 points)
        user_dom_elem_s = user_chart_data.get('sidereal_chart_analysis', {}).get('dominant_element')
        fp_dom_elem_s = fp_chart.get('sidereal_chart_analysis', {}).get('dominant_element')
        
        if user_dom_elem_s and fp_dom_elem_s:
            max_possible_score += 2.0
            if user_dom_elem_s.lower() == fp_dom_elem_s.lower():
                score += 2.0
        
        # Dominant Element - Tropical (weight: 2 points)
        user_dom_elem_t = user_chart_data.get('tropical_chart_analysis', {}).get('dominant_element')
        fp_dom_elem_t = fp_chart.get('tropical_chart_analysis', {}).get('dominant_element')
        
        if user_dom_elem_t and fp_dom_elem_t:
            max_possible_score += 2.0
            if user_dom_elem_t.lower() == fp_dom_elem_t.lower():
                score += 2.0
        
        # ========================================================================
        # CALCULATE FINAL SCORE
        # ========================================================================
        
        # Normalize to 0-100 scale based on maximum possible score
        if max_possible_score > 0:
            normalized_score = (score / max_possible_score) * 100.0
        else:
            # If max_possible_score is 0, it means no planetary placements were found to compare
            # This could happen if chart data structure is unexpected
            # Log this for debugging
            logger.warning(
                f"max_possible_score is 0 for {famous_person.name if famous_person else 'unknown'}. "
                f"Score: {score}, "
                f"User has sidereal: {bool(user_chart_data.get('sidereal_major_positions'))}, "
                f"User has tropical: {bool(user_chart_data.get('tropical_major_positions'))}, "
                f"FP has placements: {bool(fp_planetary_placements)}, "
                f"FP has chart: {bool(fp_chart)}"
            )
            # If we have matches (strict/aspect/stellium), give a minimum score
            # Otherwise return 0
            normalized_score = 0.0
        
        result = min(normalized_score, 100.0)
        return result
    
    except Exception as e:
        logger.error(f"Error calculating similarity: {e}", exc_info=True)
        return 0.0


class SimilarPeopleRequest(BaseModel):
    chart_data: Any  # Accept any type, we'll validate in endpoint
    limit: int = 10

@app.post("/api/find-similar-famous-people")
@limiter.limit("100/day")
async def find_similar_famous_people_endpoint(
    request: Request,
    data: SimilarPeopleRequest,
    db: Session = Depends(get_db)
):
    """
    Find famous people with similar birth charts to the user's chart.
    This is a FREE feature - no subscription required.
    
    Args:
        chart_data: The user's calculated chart data (from /calculate_chart endpoint)
        limit: Number of matches to return (default 10, max 50)
    
    Returns:
        List of famous people sorted by similarity score
    """
    try:
        limit = data.limit
        if limit > 50:
            limit = 50
        if limit < 1:
            limit = 10
        
        # Handle chart_data - it might come as a string (JSON) or dict
        chart_data = data.chart_data
        
        # Debug logging
        logger.info(f"Received chart_data type: {type(chart_data)}, is string: {isinstance(chart_data, str)}")
        if isinstance(chart_data, str):
            logger.info(f"chart_data string preview: {chart_data[:200]}")
        
        # Recursively parse JSON strings in nested structures
        def parse_json_recursive(obj):
            """Recursively parse JSON strings in nested structures."""
            if isinstance(obj, str):
                try:
                    parsed = json.loads(obj)
                    # If parsing succeeded, recursively parse the result
                    return parse_json_recursive(parsed)
                except (json.JSONDecodeError, TypeError):
                    # Not JSON, return as-is
                    return obj
            elif isinstance(obj, dict):
                return {k: parse_json_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [parse_json_recursive(item) for item in obj]
            else:
                return obj
        
        # Parse chart_data if it's a string
        if isinstance(chart_data, str):
            try:
                chart_data = json.loads(chart_data)
                logger.info(f"Parsed JSON string, new type: {type(chart_data)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse chart_data as JSON: {e}")
                raise HTTPException(status_code=400, detail="Invalid chart_data format - must be valid JSON")
        
        # Recursively parse any nested JSON strings (e.g., numerology, chinese_zodiac might be JSON strings)
        chart_data = parse_json_recursive(chart_data)
        
        # Debug: Log the types of nested values after recursive parsing
        if 'numerology' in chart_data:
            logger.info(f"numerology type after parsing: {type(chart_data['numerology'])}")
        if 'chinese_zodiac' in chart_data:
            logger.info(f"chinese_zodiac type after parsing: {type(chart_data['chinese_zodiac'])}")
        
        # Double-check it's a dict after parsing
        if not isinstance(chart_data, dict):
            logger.error(f"chart_data is not a dict after parsing. Type: {type(chart_data)}, Value: {str(chart_data)[:200]}")
            raise HTTPException(status_code=400, detail=f"chart_data must be a dictionary or JSON string. Got type: {type(chart_data).__name__}")
        
        # Ensure we have the expected structure
        if 'sidereal_major_positions' not in chart_data and 'tropical_major_positions' not in chart_data:
            logger.warning(f"chart_data missing expected keys. Keys present: {list(chart_data.keys())[:10]}")
        
        # Extract user's signs for filtering (optimization)
        # Safely handle missing or invalid data
        sidereal_positions = chart_data.get('sidereal_major_positions', [])
        tropical_positions = chart_data.get('tropical_major_positions', [])
        
        # Ensure positions are lists
        if not isinstance(sidereal_positions, list):
            logger.warning(f"sidereal_major_positions is not a list: {type(sidereal_positions)}")
            sidereal_positions = []
        if not isinstance(tropical_positions, list):
            logger.warning(f"tropical_major_positions is not a list: {type(tropical_positions)}")
            tropical_positions = []
        
        s_positions = {p['name']: p for p in sidereal_positions if isinstance(p, dict) and 'name' in p}
        t_positions = {p['name']: p for p in tropical_positions if isinstance(p, dict) and 'name' in p}
        
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        user_sun_s = extract_sign(s_positions.get('Sun', {}).get('position')) if 'Sun' in s_positions and s_positions['Sun'].get('position') else None
        user_sun_t = extract_sign(t_positions.get('Sun', {}).get('position')) if 'Sun' in t_positions and t_positions['Sun'].get('position') else None
        user_moon_s = extract_sign(s_positions.get('Moon', {}).get('position')) if 'Moon' in s_positions and s_positions['Moon'].get('position') else None
        user_moon_t = extract_sign(t_positions.get('Moon', {}).get('position')) if 'Moon' in t_positions and t_positions['Moon'].get('position') else None
        
        # Get user's numerology and Chinese zodiac for additional filtering
        # Safely handle nested dictionaries that might be strings or missing
        # Safely get numerology - it might be a string, dict, or missing
        numerology_data = chart_data.get('numerology')
        if numerology_data is None:
            numerology_data = {}
        elif isinstance(numerology_data, str):
            try:
                numerology_data = json.loads(numerology_data)
                # Recursively parse in case it contains more nested strings
                numerology_data = parse_json_recursive(numerology_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse numerology as JSON: {e}, value: {numerology_data[:100] if isinstance(numerology_data, str) else numerology_data}")
                numerology_data = {}
        elif not isinstance(numerology_data, dict):
            logger.warning(f"numerology is not a dict: {type(numerology_data)}")
            numerology_data = {}
        
        # Now safely get the life_path_number
        user_life_path = numerology_data.get('life_path_number') if isinstance(numerology_data, dict) else None
        
        # Safely get chinese_zodiac - it might be a string, dict, or missing
        chinese_zodiac_data = chart_data.get('chinese_zodiac')
        if chinese_zodiac_data is None:
            chinese_zodiac_data = {}
        elif isinstance(chinese_zodiac_data, str):
            try:
                chinese_zodiac_data = json.loads(chinese_zodiac_data)
                # Recursively parse in case it contains more nested strings
                chinese_zodiac_data = parse_json_recursive(chinese_zodiac_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse chinese_zodiac as JSON: {e}, value: {chinese_zodiac_data[:100] if isinstance(chinese_zodiac_data, str) else chinese_zodiac_data}")
                chinese_zodiac_data = {}
        elif not isinstance(chinese_zodiac_data, dict):
            logger.warning(f"chinese_zodiac is not a dict: {type(chinese_zodiac_data)}")
            chinese_zodiac_data = {}
        
        # Now safely get the animal
        user_chinese_animal = chinese_zodiac_data.get('animal') if isinstance(chinese_zodiac_data, dict) else None
        
        # OPTIMIZATION: Filter database query using new matching criteria
        # We'll use broader filters to catch all potential matches, then apply strict criteria
        from sqlalchemy import or_, and_
        
        # Build filter query - use OR to catch any potential matches
        query = db.query(FamousPerson)
        
        # Build conditions for potential matches
        conditions = []
        
        # 1. Sun AND Moon sidereal match
        if user_sun_s and user_moon_s:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_sidereal == user_sun_s,
                    FamousPerson.moon_sign_sidereal == user_moon_s
                )
            )
        
        # 2. Sun AND Moon tropical match
        if user_sun_t and user_moon_t:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_tropical == user_sun_t,
                    FamousPerson.moon_sign_tropical == user_moon_t
                )
            )
        
        # 3. Numerology day AND life path match
        user_day = numerology_data.get('day_number') if isinstance(numerology_data, dict) else None
        if user_day and user_life_path:
            user_day_norm = normalize_master_number(user_day)
            user_lp_norm = normalize_master_number(user_life_path)
            # Build OR conditions for master numbers
            lp_conditions = []
            for lp in user_lp_norm:
                lp_conditions.append(FamousPerson.life_path_number == lp)
            day_conditions = []
            for day in user_day_norm:
                day_conditions.append(FamousPerson.day_number == day)
            if lp_conditions and day_conditions:
                conditions.append(
                    and_(
                        or_(*lp_conditions),
                        or_(*day_conditions)
                    )
                )
        
        # 4. Chinese zodiac AND (day OR life path)
        if user_chinese_animal:
            chinese_conditions = []
            chinese_conditions.append(FamousPerson.chinese_zodiac_animal.ilike(f"%{user_chinese_animal}%"))
            
            numer_conditions = []
            if user_day:
                user_day_norm = normalize_master_number(user_day)
                for day in user_day_norm:
                    numer_conditions.append(FamousPerson.day_number == day)
            if user_life_path:
                user_lp_norm = normalize_master_number(user_life_path)
                for lp in user_lp_norm:
                    numer_conditions.append(FamousPerson.life_path_number == lp)
            
            if numer_conditions:
                conditions.append(
                    and_(
                        chinese_conditions[0],
                        or_(*numer_conditions)
                    )
                )
        
        # Also include people who might match on aspects or stelliums
        # (they need chart_data_json or top_aspects_json)
        if not conditions:
            # If no strict conditions, at least require chart data for aspect/stellium matching
            conditions.append(FamousPerson.chart_data_json.isnot(None))
        else:
            # Add aspect/stellium candidates to the OR conditions
            conditions.extend([
                FamousPerson.top_aspects_json.isnot(None),
                FamousPerson.chart_data_json.isnot(None)
            ])
        
        # Apply filters - use OR to get all potential matches
        if conditions:
            query = query.filter(or_(*conditions))
        else:
            # Fallback: at least match one sign
            sign_conditions = []
            if user_sun_s:
                sign_conditions.append(FamousPerson.sun_sign_sidereal == user_sun_s)
            if user_sun_t:
                sign_conditions.append(FamousPerson.sun_sign_tropical == user_sun_t)
            if user_moon_s:
                sign_conditions.append(FamousPerson.moon_sign_sidereal == user_moon_s)
            if user_moon_t:
                sign_conditions.append(FamousPerson.moon_sign_tropical == user_moon_t)
            if sign_conditions:
                query = query.filter(or_(*sign_conditions))
        
        # Get ALL famous people with chart data (no filtering, search entire database)
        # Only require that they have chart data for scoring
        all_famous_people = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None)
        ).all()
        
        if not all_famous_people:
            return {
                "matches": [],
                "message": "No matches found. We're constantly adding more famous people to our database. Check back soon!"
            }
        
        # Calculate comprehensive scores for ALL famous people
        matches = []
        for fp in all_famous_people:
            # Calculate comprehensive score for everyone
            comprehensive_score = calculate_comprehensive_similarity_score(chart_data, fp)
            
            # Only include if score > 0 (has actual matches)
            if comprehensive_score > 0.0:
                # Check match types for display purposes
            strict_match, strict_reasons = check_strict_matches(
                chart_data, fp, numerology_data, chinese_zodiac_data
            )
            aspect_match, aspect_reasons = check_aspect_matches(chart_data, fp)
            stellium_match, stellium_reasons = check_stellium_matches(chart_data, fp)
                
                # Combine all match reasons
                all_reasons = strict_reasons + aspect_reasons + stellium_reasons
                
                # Determine match type for display
                match_type = "strict" if strict_match else ("aspect" if aspect_match else ("stellium" if stellium_match else "general"))
                
                matches.append({
                    "famous_person": fp,
                    "similarity_score": comprehensive_score,
                    "match_reasons": all_reasons,
                    "match_type": match_type
                })
        
        # Sort by similarity score ONLY (highest first)
        matches.sort(key=lambda m: m["similarity_score"], reverse=True)
        
        # Take top 20 matches (always return top 20 from entire database)
        top_matches = matches[:20]
        
        # Helper function to extract all matching factors
        def extract_all_matching_factors(user_chart_data: dict, fp: FamousPerson, fp_planetary: dict, fp_chart: dict) -> list:
            """Extract a detailed list of all matching factors between user and famous person."""
            matches_list = []
            
            # Extract user's positions
            s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', []) if isinstance(p, dict) and 'name' in p}
            t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', []) if isinstance(p, dict) and 'name' in p}
            s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', []) if isinstance(p, dict) and 'name' in p}
            t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', []) if isinstance(p, dict) and 'name' in p}
            
            def extract_sign(position_str):
                if not position_str:
                    return None
                parts = position_str.split()
                return parts[-1] if parts else None
            
            # All planets to check
            planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
            
            # Check each planet in both systems
            for planet_name in planets:
                # Sidereal
                user_planet_s = None
                fp_planet_s = None
                
                if planet_name in s_positions:
                    user_planet_s = extract_sign(s_positions[planet_name].get('position'))
                
                if fp_planetary.get('sidereal', {}).get(planet_name):
                    fp_planet_s = fp_planetary['sidereal'][planet_name].get('sign')
                elif planet_name == 'Sun' and fp.sun_sign_sidereal:
                    fp_planet_s = fp.sun_sign_sidereal
                elif planet_name == 'Moon' and fp.moon_sign_sidereal:
                    fp_planet_s = fp.moon_sign_sidereal
                elif fp_chart.get('sidereal_major_positions'):
                    for p in fp_chart['sidereal_major_positions']:
                        if p.get('name') == planet_name:
                            fp_planet_s = extract_sign(p.get('position'))
                            break
                
                if user_planet_s and fp_planet_s and user_planet_s == fp_planet_s:
                    matches_list.append(f"{planet_name} (Sidereal)")
                
                # Tropical
                user_planet_t = None
                fp_planet_t = None
                
                if planet_name in t_positions:
                    user_planet_t = extract_sign(t_positions[planet_name].get('position'))
                
                if fp_planetary.get('tropical', {}).get(planet_name):
                    fp_planet_t = fp_planetary['tropical'][planet_name].get('sign')
                elif planet_name == 'Sun' and fp.sun_sign_tropical:
                    fp_planet_t = fp.sun_sign_tropical
                elif planet_name == 'Moon' and fp.moon_sign_tropical:
                    fp_planet_t = fp.moon_sign_tropical
                elif fp_chart.get('tropical_major_positions'):
                    for p in fp_chart['tropical_major_positions']:
                        if p.get('name') == planet_name:
                            fp_planet_t = extract_sign(p.get('position'))
                            break
                
                if user_planet_t and fp_planet_t and user_planet_t == fp_planet_t:
                    matches_list.append(f"{planet_name} (Tropical)")
            
            # Check Rising/Ascendant (if birth time known)
            if not user_chart_data.get('unknown_time') and not fp.unknown_time:
                user_rising_s = None
                user_rising_t = None
                fp_rising_s = None
                fp_rising_t = None
                
                if 'Ascendant' in s_extra:
                    asc_info = s_extra['Ascendant'].get('info', '')
                    user_rising_s = asc_info.split()[0] if asc_info else None
                
                if 'Ascendant' in t_extra:
                    asc_info = t_extra['Ascendant'].get('info', '')
                    user_rising_t = asc_info.split()[0] if asc_info else None
                
                if fp_chart.get('sidereal_additional_points'):
                    for p in fp_chart['sidereal_additional_points']:
                        if p.get('name') == 'Ascendant':
                            asc_info = p.get('info', '')
                            fp_rising_s = asc_info.split()[0] if asc_info else None
                            break
                
                if fp_chart.get('tropical_additional_points'):
                    for p in fp_chart['tropical_additional_points']:
                        if p.get('name') == 'Ascendant':
                            asc_info = p.get('info', '')
                            fp_rising_t = asc_info.split()[0] if asc_info else None
                            break
                
                if user_rising_s and fp_rising_s and user_rising_s == fp_rising_s:
                    matches_list.append("Rising/Ascendant (Sidereal)")
                
                if user_rising_t and fp_rising_t and user_rising_t == fp_rising_t:
                    matches_list.append("Rising/Ascendant (Tropical)")
            
            # Check Numerology
            user_numerology = user_chart_data.get('numerology', {})
            if isinstance(user_numerology, str):
                try:
                    user_numerology = json.loads(user_numerology)
                except:
                    user_numerology = {}
            
            user_life_path = user_numerology.get('life_path_number') if isinstance(user_numerology, dict) else None
            user_day = user_numerology.get('day_number') if isinstance(user_numerology, dict) else None
            
            if user_life_path and fp.life_path_number:
                user_lp_norm = normalize_master_number(user_life_path)
                fp_lp_norm = normalize_master_number(fp.life_path_number)
                if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                    matches_list.append(f"Life Path Number ({user_life_path})")
            
            if user_day and fp.day_number:
                user_day_norm = normalize_master_number(user_day)
                fp_day_norm = normalize_master_number(fp.day_number)
                if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                    matches_list.append(f"Day Number ({user_day})")
            
            # Check Chinese Zodiac
            user_chinese = user_chart_data.get('chinese_zodiac', {})
            if isinstance(user_chinese, str):
                try:
                    user_chinese = json.loads(user_chinese)
                except:
                    user_chinese = {}
            
            user_chinese_animal = user_chinese.get('animal') if isinstance(user_chinese, dict) else None
            if user_chinese_animal and fp.chinese_zodiac_animal:
                if user_chinese_animal.lower() == fp.chinese_zodiac_animal.lower():
                    matches_list.append(f"Chinese Zodiac ({user_chinese_animal})")
            
            # Check Dominant Element
            user_dom_elem_s = user_chart_data.get('sidereal_chart_analysis', {}).get('dominant_element')
            fp_dom_elem_s = fp_chart.get('sidereal_chart_analysis', {}).get('dominant_element')
            if user_dom_elem_s and fp_dom_elem_s and user_dom_elem_s.lower() == fp_dom_elem_s.lower():
                matches_list.append(f"Dominant Element - Sidereal ({user_dom_elem_s})")
            
            user_dom_elem_t = user_chart_data.get('tropical_chart_analysis', {}).get('dominant_element')
            fp_dom_elem_t = fp_chart.get('tropical_chart_analysis', {}).get('dominant_element')
            if user_dom_elem_t and fp_dom_elem_t and user_dom_elem_t.lower() == fp_dom_elem_t.lower():
                matches_list.append(f"Dominant Element - Tropical ({user_dom_elem_t})")
            
            # Check Aspects (from match_reasons if available, or calculate)
            user_aspects = extract_top_aspects_from_chart(user_chart_data, top_n=10)
            if fp.top_aspects_json:
                try:
                    fp_aspects = json.loads(fp.top_aspects_json)
                    
                    # Check sidereal aspects
                    user_s_aspects = user_aspects.get('sidereal', [])
                    fp_s_aspects = fp_aspects.get('sidereal', [])
                    for u_aspect in user_s_aspects:
                        for fp_aspect in fp_s_aspects:
                            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                                matches_list.append(f"Aspect (Sidereal): {u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                                break
                    
                    # Check tropical aspects
                    user_t_aspects = user_aspects.get('tropical', [])
                    fp_t_aspects = fp_aspects.get('tropical', [])
                    for u_aspect in user_t_aspects:
                        for fp_aspect in fp_t_aspects:
                            u_pair = sorted([u_aspect['p1'], u_aspect['p2']])
                            fp_pair = sorted([fp_aspect['p1'], fp_aspect['p2']])
                            if u_pair == fp_pair and u_aspect['type'] == fp_aspect['type']:
                                matches_list.append(f"Aspect (Tropical): {u_aspect['p1']} {u_aspect['type']} {u_aspect['p2']}")
                                break
                except:
                    pass
            
            return matches_list
        
        # Format response with comprehensive matching details
        result = []
        for match in top_matches:
            fp = match["famous_person"]
            
            # Get planetary placements if available
            fp_planetary = {}
            if fp.planetary_placements_json:
                try:
                    fp_planetary = json.loads(fp.planetary_placements_json)
                except:
                    pass
            
            # Get chart data
            fp_chart = {}
            if fp.chart_data_json:
                try:
                    fp_chart = json.loads(fp.chart_data_json)
                except:
                    pass
            
            # Extract all matching factors
            matching_factors = extract_all_matching_factors(chart_data, fp, fp_planetary, fp_chart)
            
            # Build match details
            match_details = {
                "name": fp.name,
                "wikipedia_url": fp.wikipedia_url,
                "occupation": fp.occupation,
                "similarity_score": round(match["similarity_score"], 1),
                "matching_factors": matching_factors,  # List of all matching factors
                "match_reasons": match.get("match_reasons", []),  # Keep for backward compatibility
                "match_type": match.get("match_type", "general"),
                "birth_date": f"{fp.birth_month}/{fp.birth_day}/{fp.birth_year}",
                "birth_location": fp.birth_location,
            }
            
            result.append(match_details)
        
        return {
            "matches": result,
            "total_compared": len(famous_people),
            "matches_found": len(result)
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error finding similar famous people: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error finding similar famous people: {str(e)}")


async def find_similar_famous_people_internal(
    chart_data: dict,
    limit: int = 10,
    db: Session = None
) -> dict:
    """
    Internal function to find similar famous people (for use in reading generation).
    Returns the same format as the endpoint but can be called internally.
    """
    if not db:
        logger.warning("No database session provided to find_similar_famous_people_internal")
        return {"matches": [], "total_compared": 0, "matches_found": 0}
    
    try:
        # Use the endpoint logic by calling it programmatically
        # We'll reuse the same matching logic
        from sqlalchemy import or_, and_
        
        # Extract user's signs (same as endpoint)
        sidereal_positions = chart_data.get('sidereal_major_positions', [])
        tropical_positions = chart_data.get('tropical_major_positions', [])
        
        s_positions = {p['name']: p for p in sidereal_positions if isinstance(p, dict) and 'name' in p}
        t_positions = {p['name']: p for p in tropical_positions if isinstance(p, dict) and 'name' in p}
        
        def extract_sign(position_str):
            if not position_str:
                return None
            parts = position_str.split()
            return parts[-1] if parts else None
        
        user_sun_s = extract_sign(s_positions.get('Sun', {}).get('position')) if 'Sun' in s_positions and s_positions['Sun'].get('position') else None
        user_sun_t = extract_sign(t_positions.get('Sun', {}).get('position')) if 'Sun' in t_positions and t_positions['Sun'].get('position') else None
        user_moon_s = extract_sign(s_positions.get('Moon', {}).get('position')) if 'Moon' in s_positions and s_positions['Moon'].get('position') else None
        user_moon_t = extract_sign(t_positions.get('Moon', {}).get('position')) if 'Moon' in t_positions and t_positions['Moon'].get('position') else None
        
        # Get numerology and Chinese zodiac
        numerology_data = chart_data.get('numerology', {})
        if isinstance(numerology_data, str):
            try:
                numerology_data = json.loads(numerology_data)
            except:
                numerology_data = {}
        if not isinstance(numerology_data, dict):
            numerology_data = {}
        
        chinese_zodiac_data = chart_data.get('chinese_zodiac', {})
        if isinstance(chinese_zodiac_data, str):
            try:
                chinese_zodiac_data = json.loads(chinese_zodiac_data)
            except:
                chinese_zodiac_data = {}
        if not isinstance(chinese_zodiac_data, dict):
            chinese_zodiac_data = {}
        
        user_life_path = numerology_data.get('life_path_number')
        user_day = numerology_data.get('day_number')
        user_chinese_animal = chinese_zodiac_data.get('animal')
        
        # Build query (same logic as endpoint)
        query = db.query(FamousPerson)
        conditions = []
        
        if user_sun_s and user_moon_s:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_sidereal == user_sun_s,
                    FamousPerson.moon_sign_sidereal == user_moon_s
                )
            )
        
        if user_sun_t and user_moon_t:
            conditions.append(
                and_(
                    FamousPerson.sun_sign_tropical == user_sun_t,
                    FamousPerson.moon_sign_tropical == user_moon_t
                )
            )
        
        if user_day and user_life_path:
            user_day_norm = normalize_master_number(user_day)
            user_lp_norm = normalize_master_number(user_life_path)
            lp_conditions = [FamousPerson.life_path_number == lp for lp in user_lp_norm]
            day_conditions = [FamousPerson.day_number == day for day in user_day_norm]
            if lp_conditions and day_conditions:
                conditions.append(and_(or_(*lp_conditions), or_(*day_conditions)))
        
        if user_chinese_animal:
            chinese_conditions = [FamousPerson.chinese_zodiac_animal.ilike(f"%{user_chinese_animal}%")]
            numer_conditions = []
            if user_day:
                user_day_norm = normalize_master_number(user_day)
                numer_conditions.extend([FamousPerson.day_number == day for day in user_day_norm])
            if user_life_path:
                user_lp_norm = normalize_master_number(user_life_path)
                numer_conditions.extend([FamousPerson.life_path_number == lp for lp in user_lp_norm])
            if numer_conditions:
                conditions.append(and_(chinese_conditions[0], or_(*numer_conditions)))
        
        if not conditions:
            conditions.append(FamousPerson.chart_data_json.isnot(None))
        else:
            conditions.extend([
                FamousPerson.top_aspects_json.isnot(None),
                FamousPerson.chart_data_json.isnot(None)
            ])
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        # Get ALL famous people with chart data (search entire database)
        all_famous_people = db.query(FamousPerson).filter(
            FamousPerson.chart_data_json.isnot(None)
        ).all()
        
        if not all_famous_people:
            return {"matches": [], "total_compared": 0, "matches_found": 0}
        
        # Calculate comprehensive scores for ALL famous people
        matches = []
        for fp in all_famous_people:
            # Calculate comprehensive score for everyone
            comprehensive_score = calculate_comprehensive_similarity_score(chart_data, fp)
            
            # Only include if score > 0 (has actual matches)
            if comprehensive_score > 0.0:
                strict_match, strict_reasons = check_strict_matches(chart_data, fp, numerology_data, chinese_zodiac_data)
                aspect_match, aspect_reasons = check_aspect_matches(chart_data, fp)
                stellium_match, stellium_reasons = check_stellium_matches(chart_data, fp)
                
                all_reasons = strict_reasons + aspect_reasons + stellium_reasons
                
                # Determine match type
                match_type = "strict" if strict_match else ("aspect" if aspect_match else ("stellium" if stellium_match else "general"))
                
                # Get planetary placements and chart data
                fp_planetary = {}
                if fp.planetary_placements_json:
                    try:
                        fp_planetary = json.loads(fp.planetary_placements_json)
                    except:
                        pass
                
                fp_chart = {}
                if fp.chart_data_json:
                    try:
                        fp_chart = json.loads(fp.chart_data_json)
                    except:
                        pass
                
                # Extract matching factors (reuse the function from endpoint scope)
                # We need to define it here or extract it
                def extract_all_matching_factors_internal(user_chart_data: dict, fp: FamousPerson, fp_planetary: dict, fp_chart: dict) -> list:
                    """Extract matching factors - same logic as endpoint."""
                    matches_list = []
                    s_positions = {p['name']: p for p in user_chart_data.get('sidereal_major_positions', []) if isinstance(p, dict) and 'name' in p}
                    t_positions = {p['name']: p for p in user_chart_data.get('tropical_major_positions', []) if isinstance(p, dict) and 'name' in p}
                    s_extra = {p['name']: p for p in user_chart_data.get('sidereal_additional_points', []) if isinstance(p, dict) and 'name' in p}
                    t_extra = {p['name']: p for p in user_chart_data.get('tropical_additional_points', []) if isinstance(p, dict) and 'name' in p}
                    
                    def extract_sign_internal(position_str):
                        if not position_str:
                            return None
                        parts = position_str.split()
                        return parts[-1] if parts else None
                    
                    planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
                    
                    for planet_name in planets:
                        # Sidereal
                        user_planet_s = None
                        fp_planet_s = None
                        if planet_name in s_positions:
                            user_planet_s = extract_sign_internal(s_positions[planet_name].get('position'))
                        if fp_planetary.get('sidereal', {}).get(planet_name):
                            fp_planet_s = fp_planetary['sidereal'][planet_name].get('sign')
                        elif planet_name == 'Sun' and fp.sun_sign_sidereal:
                            fp_planet_s = fp.sun_sign_sidereal
                        elif planet_name == 'Moon' and fp.moon_sign_sidereal:
                            fp_planet_s = fp.moon_sign_sidereal
                        elif fp_chart.get('sidereal_major_positions'):
                            for p in fp_chart['sidereal_major_positions']:
                                if p.get('name') == planet_name:
                                    fp_planet_s = extract_sign_internal(p.get('position'))
                                    break
                        if user_planet_s and fp_planet_s and user_planet_s == fp_planet_s:
                            matches_list.append(f"{planet_name} (Sidereal)")
                        
                        # Tropical
                        user_planet_t = None
                        fp_planet_t = None
                        if planet_name in t_positions:
                            user_planet_t = extract_sign_internal(t_positions[planet_name].get('position'))
                        if fp_planetary.get('tropical', {}).get(planet_name):
                            fp_planet_t = fp_planetary['tropical'][planet_name].get('sign')
                        elif planet_name == 'Sun' and fp.sun_sign_tropical:
                            fp_planet_t = fp.sun_sign_tropical
                        elif planet_name == 'Moon' and fp.moon_sign_tropical:
                            fp_planet_t = fp.moon_sign_tropical
                        elif fp_chart.get('tropical_major_positions'):
                            for p in fp_chart['tropical_major_positions']:
                                if p.get('name') == planet_name:
                                    fp_planet_t = extract_sign_internal(p.get('position'))
                                    break
                        if user_planet_t and fp_planet_t and user_planet_t == fp_planet_t:
                            matches_list.append(f"{planet_name} (Tropical)")
                    
                    # Check numerology
                    user_numerology = user_chart_data.get('numerology', {})
                    if isinstance(user_numerology, str):
                        try:
                            user_numerology = json.loads(user_numerology)
                        except:
                            user_numerology = {}
                    user_life_path = user_numerology.get('life_path_number') if isinstance(user_numerology, dict) else None
                    user_day = user_numerology.get('day_number') if isinstance(user_numerology, dict) else None
                    
                    if user_life_path and fp.life_path_number:
                        user_lp_norm = normalize_master_number(user_life_path)
                        fp_lp_norm = normalize_master_number(fp.life_path_number)
                        if any(lp in fp_lp_norm for lp in user_lp_norm) or any(lp in user_lp_norm for lp in fp_lp_norm):
                            matches_list.append(f"Life Path Number ({user_life_path})")
                    
                    if user_day and fp.day_number:
                        user_day_norm = normalize_master_number(user_day)
                        fp_day_norm = normalize_master_number(fp.day_number)
                        if any(d in fp_day_norm for d in user_day_norm) or any(d in user_day_norm for d in fp_day_norm):
                            matches_list.append(f"Day Number ({user_day})")
                    
                    # Check Chinese Zodiac
                    user_chinese = user_chart_data.get('chinese_zodiac', {})
                    if isinstance(user_chinese, str):
                        try:
                            user_chinese = json.loads(user_chinese)
                        except:
                            user_chinese = {}
                    user_chinese_animal = user_chinese.get('animal') if isinstance(user_chinese, dict) else None
                    if user_chinese_animal and fp.chinese_zodiac_animal:
                        if user_chinese_animal.lower() == fp.chinese_zodiac_animal.lower():
                            matches_list.append(f"Chinese Zodiac ({user_chinese_animal})")
                    
                    return matches_list
                
                matching_factors = extract_all_matching_factors_internal(chart_data, fp, fp_planetary, fp_chart)
                
                matches.append({
                    "famous_person": fp,
                    "similarity_score": comprehensive_score,
                    "match_reasons": all_reasons,
                    "match_type": match_type,
                    "matching_factors": matching_factors
                })
        
        # Sort by similarity score ONLY (highest first)
        matches.sort(key=lambda m: m["similarity_score"], reverse=True)
        
        # Always return top 20 from entire database
        top_matches = matches[:20]
        
        # Format response
        result = []
        for match in top_matches:
            fp = match["famous_person"]
            result.append({
                "name": fp.name,
                "occupation": fp.occupation,
                "similarity_score": round(match["similarity_score"], 1),
                "matching_factors": match.get("matching_factors", []),
                "birth_date": f"{fp.birth_month}/{fp.birth_day}/{fp.birth_year}",
                "birth_location": fp.birth_location,
            })
        
        return {
            "matches": result,
            "total_compared": len(all_famous_people),
            "matches_found": len(result)
        }
    
    except Exception as e:
        logger.error(f"Error in find_similar_famous_people_internal: {e}", exc_info=True)
        return {"matches": [], "total_compared": 0, "matches_found": 0}
