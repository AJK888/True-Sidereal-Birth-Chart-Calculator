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
from anthropic import AsyncAnthropic
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
    format_serialized_chart_for_prompt, parse_json_response
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

# --- SETUP CLAUDE ---
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
claude_client = None
if CLAUDE_API_KEY:
    try:
        claude_client = AsyncAnthropic(api_key=CLAUDE_API_KEY)
        logger.info("Claude async API client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Claude client: {e}")
        claude_client = None
else:
    logger.warning("CLAUDE_API_KEY not configured - AI reading will be unavailable unless AI_MODE=stub")

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

def format_full_report_for_email(chart_data: dict, claude_reading: str, user_inputs: dict, chart_image_base64: Optional[str], include_inputs: bool = True) -> str:
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
    html += f"<p>{claude_reading.replace('\\n', '<br><br>')}</p>"
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


def calculate_claude_cost(prompt_tokens: int, completion_tokens: int, 
                          input_price_per_million: float = 3.00, 
                          output_price_per_million: float = 15.00) -> dict:
    """
    Calculate the cost of a Claude API call based on token usage.
    
    Default prices are for Claude 3.5 Sonnet:
    - Input: $3.00 per 1M tokens
    - Output: $15.00 per 1M tokens
    
    You should verify current pricing at: https://www.anthropic.com/pricing
    
    Returns a dict with cost breakdown.
    """
    try:
        # Ensure tokens are valid integers
        prompt_tokens = int(prompt_tokens) if prompt_tokens is not None else 0
        completion_tokens = int(completion_tokens) if completion_tokens is not None else 0
        
        # Ensure non-negative
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
        logger.error(f"Error calculating Claude cost: {e}. Tokens: prompt={prompt_tokens}, completion={completion_tokens}")
        # Return safe defaults
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

class LLMClient:
    """Unified LLM client with token and cost accumulation."""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        
    async def generate(self, system: str, user: str, temperature: float = 0.7, 
                      max_output_tokens: Optional[int] = None, call_label: str = "unnamed",
                      response_format: Optional[dict] = None) -> str:
        """
        Generate LLM response with token and cost tracking.
        
        Args:
            system: System prompt
            user: User prompt/content
            temperature: Temperature setting (default 0.7)
            max_output_tokens: Max output tokens (optional)
            call_label: Label for logging (e.g., "call1_chart_overview")
        
        Returns:
            Response text
        """
        self.call_count += 1
        logger.info(f"[{call_label}] Starting LLM call #{self.call_count}")
        logger.info(f"[{call_label}] System prompt length: {len(system)} chars")
        logger.info(f"[{call_label}] User content length: {len(user)} chars")
        
        if AI_MODE == "stub":
            logger.info(f"[{call_label}] AI_MODE=stub: Returning stub response")
            stub_response = f"[STUB RESPONSE for {call_label}] This is a placeholder response for local testing. System: {system[:100]}... User: {user[:100]}..."
            # Simulate token usage for stubs
            self.total_prompt_tokens += len(system.split()) + len(user.split())
            self.total_completion_tokens += len(stub_response.split())
            return stub_response
        
        # Real LLM call
        try:
            if not CLAUDE_API_KEY or not claude_client:
                logger.error(f"[{call_label}] Claude API key not configured or client not initialized - cannot call Claude API")
                raise Exception("Claude API key not configured or client not initialized")
            
            logger.info(f"[{call_label}] Calling Claude API...")
            
            # Prepare messages for Claude API
            # Note: Claude requires system prompt as a separate parameter, not in messages array
            messages = [{"role": "user", "content": user}]
            
            # Determine max_tokens (default to 4096, allow override)
            max_tokens = max_output_tokens if max_output_tokens else 4096
            
            logger.info(f"[{call_label}] Claude model initialized, generating content (max_tokens={max_tokens})...")
            
            # Make the API call
            # Try different model name formats - Anthropic may use different naming
            # Common formats: claude-3-5-sonnet-latest, claude-3-5-sonnet-20241022, claude-3-sonnet-20240229
            # Default to claude-3-5-sonnet-latest (always uses latest Sonnet 3.5)
            claude_model = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
            logger.info(f"[{call_label}] Using Claude model: {claude_model}")
            api_kwargs = {
                "model": claude_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            # Add system parameter if provided (Claude requires this as a top-level parameter)
            if system:
                api_kwargs["system"] = system
                logger.info(f"[{call_label}] System prompt provided ({len(system)} chars)")
            
            # Note: Claude doesn't support OpenAI-style response_format.
            # For JSON mode, we rely on strong prompting in the system/user messages.
            # If response_format is provided, we'll log it but not pass it to the API.
            if response_format:
                logger.info(f"[{call_label}] JSON mode requested - relying on prompt instructions for JSON output")
            
            # Make async API call - this is non-blocking and maintains FastAPI event loop
            response = await claude_client.messages.create(**api_kwargs)
            
            logger.info(f"[{call_label}] Claude API call completed successfully")
            
            # Extract usage metadata
            usage_metadata = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0
            }
            if hasattr(response, 'usage') and response.usage:
                try:
                    usage_metadata = {
                        'prompt_tokens': getattr(response.usage, 'input_tokens', 0) or 0,
                        'completion_tokens': getattr(response.usage, 'output_tokens', 0) or 0,
                        'total_tokens': (getattr(response.usage, 'input_tokens', 0) or 0) + (getattr(response.usage, 'output_tokens', 0) or 0)
                    }
                    usage_metadata = {k: int(v) if v is not None else 0 for k, v in usage_metadata.items()}
                    logger.info(f"[{call_label}] Token usage - Input: {usage_metadata['prompt_tokens']}, Output: {usage_metadata['completion_tokens']}, Total: {usage_metadata['total_tokens']}")
                except Exception as meta_error:
                    logger.warning(f"[{call_label}] Error extracting usage metadata: {meta_error}. Using defaults.")
                    usage_metadata = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
            
            # Accumulate tokens
            self.total_prompt_tokens += usage_metadata['prompt_tokens']
            self.total_completion_tokens += usage_metadata['completion_tokens']
            
            # Calculate and accumulate cost
            cost_info = calculate_claude_cost(usage_metadata['prompt_tokens'], usage_metadata['completion_tokens'])
            self.total_cost_usd += cost_info['total_cost_usd']
            logger.info(f"[{call_label}] Call cost: ${cost_info['total_cost_usd']:.6f} (Input: ${cost_info['input_cost_usd']:.6f}, Output: ${cost_info['output_cost_usd']:.6f})")
            
            # Extract response text
            if not hasattr(response, 'content') or not response.content:
                raise Exception("Claude response has no content available")
            
            # Claude returns content as a list of content blocks
            text_parts = []
            for content_block in response.content:
                if hasattr(content_block, 'text') and content_block.text:
                    text_parts.append(content_block.text)
                elif hasattr(content_block, 'type') and content_block.type == 'text' and hasattr(content_block, 'text'):
                    text_parts.append(content_block.text)
            
            response_text = ' '.join(text_parts).strip() if text_parts else ""
            if not response_text:
                raise Exception("Claude response has no text content available")
            
            logger.info(f"[{call_label}] Response length: {len(response_text)} characters")
            return response_text
            
        except Exception as e:
            logger.error(f"[{call_label}] Error in Claude API call: {e}", exc_info=True)
            error_str = str(e).lower()
            error_message = f"An error occurred during a Claude API call: {e}"
            
            # Handle specific error types
            if any(keyword in error_str for keyword in ['quota', 'credit', 'billing', 'payment', 'insufficient']):
                error_message = "API quota or credits exhausted. Please check your Claude API billing and quota limits."
                logger.error(f"[{call_label}] Claude API quota/credit error detected")
            elif any(keyword in error_str for keyword in ['rate limit', '429', 'too many requests']):
                error_message = "API rate limit exceeded. Please wait a moment and try again."
                logger.error(f"[{call_label}] Claude API rate limit error detected")
            elif any(keyword in error_str for keyword in ['permission', 'unauthorized', 'authentication', 'invalid api key', 'api key']):
                error_message = "API authentication error. Please check your Claude API key configuration."
                logger.error(f"[{call_label}] Claude API authentication error detected")
            elif "content_filter" in error_str or "safety" in error_str:
                error_message = f"Error: The AI's response was filtered due to content policy. Please try rephrasing or contact support."
                logger.error(f"[{call_label}] Claude content filter triggered")
            
            raise Exception(error_message)
    
    def get_summary(self) -> dict:
        """Get summary of token usage and costs."""
        return {
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_prompt_tokens + self.total_completion_tokens,
            'total_cost_usd': self.total_cost_usd,
            'call_count': self.call_count
        }


async def _run_gemini_prompt(prompt_text: str) -> tuple[str, dict]:
    """
    Run a Gemini API prompt and return both the response text and usage metadata.
    Returns: (response_text, usage_metadata) where usage_metadata contains 'prompt_tokens' and 'completion_tokens'
    """
    try:
        if not GEMINI_API_KEY:
            logger.error("Gemini API key not configured - cannot call Gemini API")
            raise Exception("Gemini API key not configured")
        
        logger.info(f"Calling Gemini API with prompt length: {len(prompt_text)} characters")
        model = genai.GenerativeModel('gemini-2.5-pro')
        logger.info("Gemini model initialized, generating content...")
        response = await model.generate_content_async(prompt_text)
        logger.info("Gemini API call completed successfully")
        # Add basic error checking for empty or blocked responses
        if not response.parts:
             # Check for safety feedback which might indicate blocking
            safety_feedback = response.prompt_feedback if hasattr(response, 'prompt_feedback') else "No feedback available."
            logger.error(f"Gemini response blocked or empty. Safety Feedback: {safety_feedback}. Prompt: {prompt_text[:500]}...") # Log beginning of prompt
            # Raise exception instead of returning error string
            raise Exception(f"Gemini response was blocked or empty. Feedback: {safety_feedback}")
        
        # Extract usage metadata if available
        usage_metadata = {
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0
        }
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            try:
                # Try multiple possible attribute names for token counts
                usage_metadata = {
                    'prompt_tokens': getattr(response.usage_metadata, 'prompt_token_count', 0) or 0,
                    'completion_tokens': getattr(response.usage_metadata, 'candidates_token_count', 
                                                getattr(response.usage_metadata, 'completion_token_count', 0)) or 0,
                    'total_tokens': getattr(response.usage_metadata, 'total_token_count', 0) or 0
                }
                # Ensure all values are integers, not None
                usage_metadata = {k: int(v) if v is not None else 0 for k, v in usage_metadata.items()}
                logger.info(f"Token usage - Input: {usage_metadata['prompt_tokens']}, Output: {usage_metadata['completion_tokens']}, Total: {usage_metadata['total_tokens']}")
            except Exception as meta_error:
                logger.warning(f"Error extracting usage metadata: {meta_error}. Using defaults.")
                usage_metadata = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        
        # Safely extract response text
        if not hasattr(response, 'text') or response.text is None:
            # Try to get text from parts
            text_parts = []
            if hasattr(response, 'parts') and response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        text_parts.append(part.text)
            response_text = ' '.join(text_parts).strip() if text_parts else ""
            if not response_text:
                raise Exception("Gemini response has no text content available")
        else:
            response_text = response.text.strip()
        
        return response_text, usage_metadata
    except Exception as e:
        logger.error(f"Error in Gemini API call: {e}", exc_info=True)
        # Check for specific error types
        error_str = str(e).lower()
        error_message = f"An error occurred during a Gemini API call: {e}"
        
        # Handle quota/credit errors
        if any(keyword in error_str for keyword in ['quota', 'credit', 'billing', 'payment', 'insufficient']):
            error_message = "API quota or credits exhausted. Please check your Gemini API billing and quota limits."
            logger.error("Gemini API quota/credit error detected")
        
        # Handle rate limiting
        elif any(keyword in error_str for keyword in ['rate limit', '429', 'too many requests']):
            error_message = "API rate limit exceeded. Please wait a moment and try again."
            logger.error("Gemini API rate limit error detected")
        
        # Handle permission/authentication errors
        elif any(keyword in error_str for keyword in ['permission', 'unauthorized', 'authentication', 'invalid api key', 'api key']):
            error_message = "API authentication error. Please check your Gemini API key configuration."
            logger.error("Gemini API authentication error detected")
        
        # Handle blocked responses
        elif "response was blocked" in error_str or "blocked" in error_str:
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

async def call1_chart_overview_and_themes(llm: LLMClient, serialized_chart: dict, chart_summary: str, 
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
        max_output_tokens=4096,
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


async def call2_full_section_drafts(llm: LLMClient, serialized_chart: dict, chart_summary: str,
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


async def call3_polish_reading(llm: LLMClient, draft_reading: str, chart_summary: str) -> str:
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


async def get_claude_reading(chart_data: dict, unknown_time: bool) -> str:
    """
    Generate comprehensive astrological reading using exactly 3 Claude API calls.
    
    Call 1: Deep Chart Analysis → Chart JSON blueprint
    Call 2: Full Draft Reading (using JSON plan)
    Call 3: Lightweight Polish
    """
    if not CLAUDE_API_KEY and AI_MODE != "stub":
        logger.error("Claude API key not configured - AI reading unavailable")
        raise Exception("Claude API key not configured. AI reading is unavailable.")

    logger.info("="*60)
    logger.info("Starting Claude reading generation...")
    logger.info(f"AI_MODE: {AI_MODE}")
    logger.info(f"Unknown time: {unknown_time}")
    logger.info("="*60)
    
    # Initialize LLM client for token/cost tracking
    llm = LLMClient()
    
    try:
        # Serialize chart data for LLM consumption
        serialized_chart = serialize_chart_for_llm(chart_data, unknown_time=unknown_time)
        chart_summary = format_serialized_chart_for_prompt(serialized_chart)
        
        # Call 1: Chart Overview and Core Themes
        chart_overview = await call1_chart_overview_and_themes(
            llm, serialized_chart, chart_summary, unknown_time
        )
        
        # Call 2: Full Section Drafts
        draft_reading = await call2_full_section_drafts(
            llm, serialized_chart, chart_summary, chart_overview, unknown_time
        )
        
        # Call 3: Polish Reading
        final_reading = await call3_polish_reading(
            llm, draft_reading, chart_summary
        )
        
        # Log final cost summary
        summary = llm.get_summary()
        logger.info(">>> ENTERED get_claude_reading AND ABOUT TO LOG COST <<<")
        cost_info = calculate_claude_cost(summary['total_prompt_tokens'], summary['total_completion_tokens'])
        logger.info(f"=== CLAUDE API COST SUMMARY ===")
        logger.info(f"Total Calls: {summary['call_count']}")
        logger.info(f"Total Input Tokens: {summary['total_prompt_tokens']:,}")
        logger.info(f"Total Output Tokens: {summary['total_completion_tokens']:,}")
        logger.info(f"Total Tokens: {summary['total_tokens']:,}")
        logger.info(f"Input Cost: ${cost_info['input_cost_usd']:.6f}")
        logger.info(f"Output Cost: ${cost_info['output_cost_usd']:.6f}")
        logger.info(f"TOTAL COST: ${cost_info['total_cost_usd']:.6f}")
        logger.info("=" * 50)
        # Also print to stdout as fallback
        print(f"\n{'='*60}")
        print(f"CLAUDE API COST SUMMARY")
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
        logger.error(f"Error during Claude reading generation: {e}", exc_info=True)
        # Log which call failed if possible
        if "call1" in str(e).lower():
            logger.error("Call 1 (Chart Overview) failed")
        elif "call2" in str(e).lower():
            logger.error("Call 2 (Full Section Drafts) failed")
        elif "call3" in str(e).lower():
            logger.error("Call 3 (Polish Reading) failed")
        raise Exception(f"An error occurred while generating the detailed AI reading: {e}")


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
            claude_reading = await get_claude_reading(chart_data, unknown_time)
            logger.info(f"AI Reading successfully generated for: {chart_name} (length: {len(claude_reading)} characters)")
            
            # Store reading in cache for frontend retrieval
            chart_hash = generate_chart_hash(chart_data, unknown_time)
            reading_cache[chart_hash] = {
                'reading': claude_reading,
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
            pdf_bytes = generate_pdf_report(chart_data, claude_reading, user_inputs)
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


async def send_emails_in_background(chart_data: Dict, claude_reading: str, user_inputs: Dict):
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
            pdf_bytes = generate_pdf_report(chart_data, claude_reading, user_inputs)
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
@limiter.limit("3/month")
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
