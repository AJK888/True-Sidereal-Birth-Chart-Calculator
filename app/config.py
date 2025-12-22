"""
Centralized configuration management.

This module provides a single source of truth for all environment variables
and configuration settings used throughout the application.
"""

import os
from typing import Optional
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# ============================================================
# API Configuration
# ============================================================

# API Base URL (for external API calls)
API_BASE_URL = os.getenv("API_BASE_URL", "https://true-sidereal-api.onrender.com")

# ============================================================
# Database Configuration
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./astrology.db")

# ============================================================
# Authentication & Security
# ============================================================

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

# Admin/Friends & Family Key
ADMIN_SECRET_KEY = os.getenv("FRIENDS_AND_FAMILY_KEY")

# ============================================================
# LLM/AI Configuration
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AI_MODE = os.getenv("AI_MODE", "real").lower()  # "real" or "stub" for local testing

# ============================================================
# Email Configuration (SendGrid)
# ============================================================

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# ============================================================
# Payment Configuration (Stripe)
# ============================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# ============================================================
# Geocoding Configuration
# ============================================================

OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "SynthesisAstrology/1.0 (contact@example.com)")

# ============================================================
# Swiss Ephemeris Configuration
# ============================================================

SWEP_PATH = os.getenv("SWEP_PATH")
DEFAULT_SWISS_EPHEMERIS_PATH = BASE_DIR / "swiss_ephemeris"

# ============================================================
# Deployment Configuration
# ============================================================

WEBPAGE_DEPLOY_HOOK_URL = os.getenv("WEBPAGE_DEPLOY_HOOK_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # development, staging, production

# ============================================================
# Logging Configuration
# ============================================================

LOGTAIL_API_KEY = os.getenv("LOGTAIL_API_KEY")  # Also known as LOGTAIL_SOURCE_TOKEN
LOGTAIL_HOST = os.getenv("LOGTAIL_HOST")
LOGTAIL_PORT = int(os.getenv("LOGTAIL_PORT", "0")) if os.getenv("LOGTAIL_PORT") else None
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ============================================================
# Cache Configuration
# ============================================================

CACHE_EXPIRY_HOURS = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))

# ============================================================
# Rate Limiting Configuration
# ============================================================

# Default rate limits (can be overridden per endpoint)
DEFAULT_RATE_LIMIT = os.getenv("DEFAULT_RATE_LIMIT", "100/hour")

# ============================================================
# Validation Functions
# ============================================================

def validate_config() -> list[str]:
    """
    Validate that required configuration is present.
    Returns a list of missing required configuration keys.
    """
    errors = []
    
    # Required for production
    if ENVIRONMENT == "production":
        if not SECRET_KEY or SECRET_KEY == "your-secret-key-change-in-production":
            errors.append("SECRET_KEY must be set in production")
        if not GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")
        if not SENDGRID_API_KEY:
            errors.append("SENDGRID_API_KEY is required for email functionality")
        if not SENDGRID_FROM_EMAIL:
            errors.append("SENDGRID_FROM_EMAIL is required for email functionality")
    
    return errors

def get_config_summary() -> dict:
    """Get a summary of configuration (without sensitive values)."""
    return {
        "environment": ENVIRONMENT,
        "api_base_url": API_BASE_URL,
        "database_configured": bool(DATABASE_URL),
        "gemini_configured": bool(GEMINI_API_KEY),
        "sendgrid_configured": bool(SENDGRID_API_KEY and SENDGRID_FROM_EMAIL),
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "admin_key_configured": bool(ADMIN_SECRET_KEY),
        "opencage_configured": bool(OPENCAGE_KEY),
        "swep_path": str(SWEP_PATH) if SWEP_PATH else str(DEFAULT_SWISS_EPHEMERIS_PATH),
    }

