"""
API Module - Main FastAPI Application

NOTE: Many functions have been extracted to service modules:
- LLM functions: app.services.llm_service, app.services.llm_prompts
- Email functions: app.services.email_service
- Chart formatting: app.services.chart_service

All prompts and calculations are preserved exactly in their respective service modules.
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Import custom exceptions and responses
from app.core.exceptions import (
    ChartCalculationError,
    GeocodingError,
    ReadingGenerationError,
    EmailError,
    LLMError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError
)
from app.core.responses import success_response, error_response
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

# --- Import Extracted Services ---
# LLM Service
from app.services.llm_service import (
    Gemini3Client,
    calculate_gemini3_cost,
    _blueprint_to_json,
    serialize_snapshot_data,
    format_snapshot_for_prompt,
    sanitize_reading_text,
    _sign_from_position
)

# LLM Prompts (all prompt functions preserved exactly)
from app.services.llm_prompts import (
    g0_global_blueprint,
    g1_natal_foundation,
    g2_deep_dive_chapters,
    g3_polish_full_reading,
    g4_famous_people_section,
    generate_snapshot_reading,
    get_gemini3_reading,
    generate_comprehensive_synastry
)

# Email Service
from app.services.email_service import (
    send_snapshot_email_via_sendgrid,
    send_chart_email_via_sendgrid,
    send_synastry_email
)

# Chart Service (formatting/utility functions only, no calculations)
from app.services.chart_service import (
    generate_chart_hash,
    get_full_text_report,
    format_full_report_for_email,
    get_quick_highlights,
    parse_pasted_chart_data
)

# --- SETUP THE LOGGER ---
from app.core.logging_config import setup_logger

logger = setup_logger("api")

# --- Import centralized configuration ---
from app.config import (
    GEMINI_API_KEY, AI_MODE, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, 
    ADMIN_EMAIL, ADMIN_SECRET_KEY, SWEP_PATH, DEFAULT_SWISS_EPHEMERIS_PATH,
    BASE_DIR as CONFIG_BASE_DIR, WEBPAGE_DEPLOY_HOOK_URL, OPENCAGE_KEY
)

# --- SETUP GEMINI ---
GEMINI3_MODEL = os.getenv("GEMINI3_MODEL", "gemini-3-pro-preview")  # Model name not in config yet
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
# SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, ADMIN_EMAIL imported from app.config above

# --- Swiss Ephemeris configuration ---
# Use BASE_DIR from config, but fallback to current file's directory for compatibility
import pathlib
BASE_DIR = str(CONFIG_BASE_DIR) if CONFIG_BASE_DIR.exists() else os.path.dirname(os.path.abspath(__file__))
# SWEP_PATH and DEFAULT_SWISS_EPHEMERIS_PATH imported from app.config above
# Convert Path objects to strings for compatibility with existing code
if isinstance(DEFAULT_SWISS_EPHEMERIS_PATH, pathlib.Path):
    DEFAULT_SWISS_EPHEMERIS_PATH = str(DEFAULT_SWISS_EPHEMERIS_PATH)

# --- Admin Secret Key for bypassing rate limit ---
# ADMIN_SECRET_KEY imported from app.config above

# --- Reading Cache for Frontend Polling ---
# Import from shared cache module
from app.core.cache import reading_cache, CACHE_EXPIRY_HOURS

# NOTE: generate_chart_hash() has been moved to app.services.chart_service
# Imported above from app.services.chart_service

# --- Rate Limiter Key Function ---
def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key for a request.
    
    Priority:
    1. Admin secret key (bypass rate limiting)
    2. Authenticated user ID (per-user rate limiting)
    3. IP address (anonymous users)
    """
    # Check for admin secret key bypass
    if ADMIN_SECRET_KEY:
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            # Check headers (case-insensitive)
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key and friends_and_family_key == ADMIN_SECRET_KEY:
            return str(uuid.uuid4())  # Unique key per request (bypass rate limiting)
    
    # Try to get authenticated user ID for per-user rate limiting
    try:
        # Check if user is authenticated via JWT token
        from fastapi.security import HTTPBearer
        from jose import jwt, JWTError
        from app.config import SECRET_KEY
        
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                user_id = payload.get("sub")
                if user_id:
                    return f"user:{user_id}"  # Per-user rate limiting
            except (JWTError, Exception):
                pass  # Invalid token, fall back to IP
    except Exception:
        pass  # Fall back to IP if anything fails
    
    # Fall back to IP address for anonymous users
    return get_remote_address(request)


# --- SETUP FASTAPI APP & RATE LIMITER ---
limiter = Limiter(key_func=get_rate_limit_key)
app = FastAPI(
    title="Synthesis Astrology API",
    version="1.0.0",
    description="""
    ## Synthesis Astrology - True Sidereal Birth Chart API
    
    A comprehensive API for calculating true sidereal birth charts, generating astrological readings,
    and finding similar famous people based on astrological compatibility.
    
    ### Features
    
    * **Chart Calculation**: Calculate complete birth charts with sidereal and tropical placements
    * **AI Readings**: Generate personalized astrological readings using AI
    * **Famous People Matching**: Find famous people with similar astrological charts
    * **Synastry Analysis**: Compare two birth charts for relationship compatibility
    * **Chart Management**: Save and retrieve saved charts
    
    ### Authentication
    
    Most endpoints support optional authentication. Some features require authentication:
    - Saving charts
    - Accessing saved charts
    - Subscription features
    
    ### Rate Limiting
    
    - Chart calculations: 200 requests per day per IP
    - Other endpoints: Varies by endpoint
    
    ### Documentation
    
    - Interactive API docs: `/docs` (Swagger UI)
    - Alternative docs: `/redoc` (ReDoc)
    """,
    terms_of_service="https://synthesisastrology.com/terms",
    contact={
        "name": "Synthesis Astrology Support",
        "email": "support@synthesisastrology.com",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=[
        {
            "name": "charts",
            "description": "Chart calculation and reading generation endpoints. Calculate birth charts with sidereal and tropical placements, aspects, numerology, and Chinese zodiac.",
        },
        {
            "name": "auth",
            "description": "Authentication endpoints. Register, login, and manage user accounts.",
        },
        {
            "name": "saved-charts",
            "description": "Saved charts management. Save, retrieve, update, and delete saved birth charts.",
        },
        {
            "name": "subscriptions",
            "description": "Subscription and payment management endpoints.",
        },
        {
            "name": "utilities",
            "description": "Utility endpoints for health checks, metrics, and configuration.",
        },
        {
            "name": "synastry",
            "description": "Synastry analysis endpoints for comparing two birth charts.",
        },
        {
            "name": "famous-people",
            "description": "Find famous people with similar astrological charts to your own.",
        },
        {
            "name": "chat",
            "description": "Chat endpoints for interacting with saved charts.",
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter

# --- Include Chat API Router ---
app.include_router(chat_router)

# --- Include Famous People Router ---
app.include_router(famous_people_router)

# --- Include API v1 Routers ---
from app.api.v1 import utilities, charts, auth, saved_charts, subscriptions, synastry

# Share limiter instance with routers
# Update router modules to use the main app limiter
charts.limiter = limiter
utilities.limiter = limiter

# Utilities (root level endpoints - no prefix for ping/root, /api for log-clicks)
app.include_router(utilities.router)
app.include_router(utilities.api_router)

# Charts (chart calculation and reading endpoints)
app.include_router(charts.router)

# Auth (authentication endpoints)
app.include_router(auth.router)

# Saved Charts (CRUD operations)
app.include_router(saved_charts.router)

# Subscriptions (subscription and payment endpoints)
app.include_router(subscriptions.router)

# Synastry (synastry analysis endpoint)
app.include_router(synastry.router)

# --- Initialize Database ---
init_db()
logger.info("Database initialized successfully")

# --- Startup Event: Trigger Webpage Deployment ---
@app.on_event("startup")
async def trigger_webpage_deployment():
    """Trigger webpage deployment when API service starts (after new deployment)."""
    # WEBPAGE_DEPLOY_HOOK_URL imported from app.config above
    
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


@app.on_event("startup")
async def startup_health_check():
    """Perform health checks on startup and log status."""
    try:
        from app.utils.health import get_comprehensive_health
        health = get_comprehensive_health()
        
        logger.info("=" * 60)
        logger.info("Startup Health Check")
        logger.info("=" * 60)
        logger.info(f"Overall Status: {health['status']}")
        
        for component, check in health['checks'].items():
            status = check.get('status', 'unknown')
            logger.info(f"{component.capitalize()}: {status}")
            if check.get('error'):
                logger.warning(f"  Error: {check['error']}")
        
        logger.info("=" * 60)
        
        if health['status'] == 'unhealthy':
            logger.error("CRITICAL: Service started with unhealthy dependencies!")
    except Exception as e:
        logger.warning(f"Startup health check failed: {e}")


@app.on_event("shutdown")
async def graceful_shutdown():
    """
    Graceful shutdown handler.
    
    Closes database connections, cache connections, and performs cleanup.
    """
    logger.info("=" * 60)
    logger.info("Graceful Shutdown Initiated")
    logger.info("=" * 60)
    
    try:
        # Close database connections
        from database import engine
        logger.info("Closing database connections...")
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    try:
        # Close Redis connection if available
        from app.core.cache import _redis_client
        if _redis_client:
            logger.info("Closing Redis connection...")
            _redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.warning(f"Error closing Redis connection: {e}")
    
    logger.info("Graceful shutdown complete")
    logger.info("=" * 60)

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

# --- Performance Monitoring Middleware ---
from app.core.performance_middleware import PerformanceMonitoringMiddleware

# Add middleware in reverse execution order (last added = first executed on response)
# Execution order on response (reverse of addition):
# 1. ApiNoCacheMiddleware (added last, executes first - can override cache headers)
# 2. SecurityHeadersMiddleware (added second, executes second - sets security defaults)
# 3. NormalizeJsonContentTypeMiddleware (added third, executes third - normalizes content-type)
# 4. PerformanceMonitoringMiddleware (added first, executes last - tracks performance)
app.add_middleware(PerformanceMonitoringMiddleware)
app.add_middleware(NormalizeJsonContentTypeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ApiNoCacheMiddleware)

# --- Import Custom Exceptions and Responses ---
from app.core.exceptions import (
    ChartCalculationError,
    GeocodingError,
    ReadingGenerationError,
    EmailError,
    LLMError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError
)
from app.core.responses import success_response, error_response

# --- Custom Exception Handlers ---
@app.exception_handler(ChartCalculationError)
async def chart_calculation_error_handler(request: Request, exc: ChartCalculationError):
    """Handle chart calculation errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Chart calculation failed",
            detail=exc.detail
        )
    )

@app.exception_handler(GeocodingError)
async def geocoding_error_handler(request: Request, exc: GeocodingError):
    """Handle geocoding errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Geocoding failed",
            detail=exc.detail
        )
    )

@app.exception_handler(ReadingGenerationError)
async def reading_generation_error_handler(request: Request, exc: ReadingGenerationError):
    """Handle reading generation errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Reading generation failed",
            detail=exc.detail
        )
    )

@app.exception_handler(EmailError)
async def email_error_handler(request: Request, exc: EmailError):
    """Handle email sending errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Email sending failed",
            detail=exc.detail
        )
    )

@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Handle LLM API errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="LLM service error",
            detail=exc.detail
        )
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Validation failed",
            detail=exc.detail
        )
    )

@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Authentication failed",
            detail=exc.detail
        )
    )

@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    """Handle authorization errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Not authorized",
            detail=exc.detail
        )
    )

@app.exception_handler(NotFoundError)
async def not_found_error_handler(request: Request, exc: NotFoundError):
    """Handle not found errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(
            error="Resource not found",
            detail=exc.detail
        )
    )

@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Thank you for using Synthesis Astrology. Due to high API costs we limit user's requests for readings. Please reach out to the developer if you would like them to provide you a reading."}
    )

# ============================================================
# OLD ENDPOINTS - MOVED TO app.api.v1.utilities
# ============================================================
# These endpoints have been moved to app/api/v1/utilities.py
# Keeping commented for reference - can be removed after verification

# @app.api_route("/ping", methods=["GET", "HEAD"])
# def ping():
#     return {"message": "ok"}


# @app.get("/")
# def root():
#     """Simple root endpoint so uptime monitors don't hit a 404."""
#     return {"message": "ok"}


# @app.get("/check_email_config")
# def check_email_config():
#     """Diagnostic endpoint to check SendGrid email configuration."""
#     config_status = {
#         "sendgrid_api_key": {
#             "configured": bool(SENDGRID_API_KEY),
#             "length": len(SENDGRID_API_KEY) if SENDGRID_API_KEY else 0,
#             "preview": f"{SENDGRID_API_KEY[:10]}..." if SENDGRID_API_KEY and len(SENDGRID_API_KEY) > 10 else "Not set"
#         },
#         "sendgrid_from_email": {
#             "configured": bool(SENDGRID_FROM_EMAIL),
#             "value": SENDGRID_FROM_EMAIL if SENDGRID_FROM_EMAIL else "Not set"
#         },
#         "admin_email": {
#             "configured": bool(ADMIN_EMAIL),
#             "value": ADMIN_EMAIL if ADMIN_EMAIL else "Not set"
#         },
#         "email_sending_ready": bool(SENDGRID_API_KEY and SENDGRID_FROM_EMAIL)
#     }
#     
#     # Log the configuration check
#     logger.info("="*60)
#     logger.info("Email Configuration Check")
#     logger.info("="*60)
#     logger.info(f"SENDGRID_API_KEY configured: {config_status['sendgrid_api_key']['configured']} (length: {config_status['sendgrid_api_key']['length']})")
#     logger.info(f"SENDGRID_FROM_EMAIL configured: {config_status['sendgrid_from_email']['configured']} (value: {config_status['sendgrid_from_email']['value']})")
#     logger.info(f"ADMIN_EMAIL configured: {config_status['admin_email']['configured']} (value: {config_status['admin_email']['value']})")
#     logger.info(f"Email sending ready: {config_status['email_sending_ready']}")
#     logger.info("="*60)
#     
#     return config_status

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

class SynastryRequest(BaseModel):
    person1_data: str
    person2_data: str
    user_email: str

# --- Functions ---
# NOTE: Many functions have been moved to service modules and are imported above.
# The following functions are now provided by:
# - Chart formatting: app.services.chart_service
# - LLM functions: app.services.llm_service, app.services.llm_prompts
# - Email functions: app.services.email_service
#
# ⚠️ DUPLICATE FUNCTION DEFINITIONS BELOW - These are imported from services above.
# The local definitions shadow the imports. They can be safely removed after verification.
# Functions to remove: calculate_gemini3_cost, Gemini3Client, _blueprint_to_json,
# g0_global_blueprint, g1_natal_foundation, g2_deep_dive_chapters, g3_polish_full_reading,
# g4_famous_people_section, serialize_snapshot_data, format_snapshot_for_prompt,
# generate_snapshot_reading, get_gemini3_reading, sanitize_reading_text,
# get_quick_highlights, send_snapshot_email_via_sendgrid, send_chart_email_via_sendgrid,
# send_synastry_email, parse_pasted_chart_data, generate_comprehensive_synastry

def _safe_get_tokens(usage: dict, key: str) -> int:
    """Safely extract token count from usage metadata, handling None and invalid values."""
    if not usage or not isinstance(usage, dict):
        return 0
    value = usage.get(key, 0)
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


# NOTE: calculate_gemini3_cost() moved to app.services.llm_service - imported above

# --- Unified LLM Client ---
# AI_MODE imported from app.config above

# NOTE: Gemini3Client class moved to app.services.llm_service - imported above

# NOTE: _blueprint_to_json() moved to app.services.llm_service - imported above


# NOTE: g0_global_blueprint() moved to app.services.llm_prompts - imported above


# NOTE: g1_natal_foundation() moved to app.services.llm_prompts - imported above

# NOTE: g2_deep_dive_chapters() moved to app.services.llm_prompts - imported above

# NOTE: g3_polish_full_reading() moved to app.services.llm_prompts - imported above

# NOTE: g4_famous_people_section() moved to app.services.llm_prompts - imported above

# NOTE: serialize_snapshot_data() moved to app.services.llm_service - imported above

# NOTE: format_snapshot_for_prompt() moved to app.services.llm_service - imported above

# NOTE: generate_snapshot_reading() moved to app.services.llm_prompts - imported above

# NOTE: get_gemini3_reading() moved to app.services.llm_prompts - imported above

# NOTE: sanitize_reading_text() moved to app.services.llm_service - imported above

def _sign_from_position(pos: str | None) -> str | None:
    """Extract sign from a position string like '12°34' Virgo'."""
    if not pos or pos == "N/A":
        return None
    parts = pos.split()
    return parts[-1] if parts else None


# NOTE: get_quick_highlights() moved to app.services.chart_service - imported above

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


# NOTE: send_snapshot_email_via_sendgrid() moved to app.services.email_service - imported above

# NOTE: send_chart_email_via_sendgrid() moved to app.services.email_service - imported above

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


# ============================================================
# OLD ENDPOINTS REMOVED - MOVED TO app.api.v1 routers
# ============================================================
# The following endpoints have been moved to routers:
# - Charts endpoints -> app/api/v1/charts.py
# - Auth endpoints -> app/api/v1/auth.py  
# - Saved charts endpoints -> app/api/v1/saved_charts.py
# - Subscription endpoints -> app/api/v1/subscriptions.py
# - Utility endpoints -> app/api/v1/utilities.py
# 
# Old endpoint functions have been removed to avoid duplication.
# All endpoints are now served through the routers included above.


# ============================================================
# CHAT WITH GEMINI ENDPOINTS
# ============================================================
# Note: Chat endpoints remain in api.py (not migrated to routers yet)



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


# @app.post("/api/log-clicks")
# Old log_clicks_endpoint removed - moved to app/api/v1/utilities.py


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
# Subscription Management Endpoints - MOVED TO app/api/v1/subscriptions.py
# ============================================================
# Old subscription endpoints removed - moved to app/api/v1/subscriptions.py
# ============================================================
# Synastry Analysis Endpoint
# ============================================================

# NOTE: parse_pasted_chart_data() moved to app.services.chart_service - imported above

# NOTE: generate_comprehensive_synastry() moved to app.services.llm_prompts - imported above

# NOTE: send_synastry_email() moved to app.services.email_service - imported above

async def synastry_endpoint(
    request: Request,
    data: SynastryRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Comprehensive synastry analysis endpoint.
    Only accessible with FRIENDS_AND_FAMILY_KEY.
    """
    # Check for FRIENDS_AND_FAMILY_KEY
    friends_and_family_key = None
    # Check query params first
    if hasattr(request, 'query_params'):
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
    # Also check URL directly
    if not friends_and_family_key and hasattr(request, 'url'):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(str(request.url))
        params = parse_qs(parsed.query)
        if 'FRIENDS_AND_FAMILY_KEY' in params:
            friends_and_family_key = params['FRIENDS_AND_FAMILY_KEY'][0]
    # Check headers
    if not friends_and_family_key:
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "x-friends-and-family-key":
                friends_and_family_key = header_value
                break
    
    # ADMIN_SECRET_KEY imported from app.config above
    if not friends_and_family_key or not ADMIN_SECRET_KEY or friends_and_family_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Synastry analysis requires friends and family access")
    
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    logger.info("="*80)
    logger.info("SYNANSTRY ANALYSIS REQUEST RECEIVED")
    logger.info("="*80)
    logger.info(f"User email: {data.user_email}")
    logger.info(f"Person 1 data length: {len(data.person1_data)} chars")
    logger.info(f"Person 2 data length: {len(data.person2_data)} chars")
    
    try:
        # Parse the pasted data
        logger.info("Parsing Person 1 data...")
        person1_parsed = parse_pasted_chart_data(data.person1_data)
        
        logger.info("Parsing Person 2 data...")
        person2_parsed = parse_pasted_chart_data(data.person2_data)
        
        # Initialize LLM client
        llm = Gemini3Client()
        
        # Generate comprehensive synastry analysis
        logger.info("Generating comprehensive synastry analysis...")
        analysis = await generate_comprehensive_synastry(llm, person1_parsed, person2_parsed)
        
        # Send email in background
        background_tasks.add_task(send_synastry_email, analysis, data.user_email)
        
        logger.info("Synastry analysis completed successfully")
        
        return {
            "status": "success",
            "analysis": analysis,
            "message": "Analysis complete. Email sent to your address."
        }
        
    except Exception as e:
        logger.error(f"Error generating synastry analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating synastry analysis: {str(e)}")

# Famous People Similarity Matching endpoint has been moved to routers/famous_people_routes.py
# The internal function has been moved to services/similarity_service.py
