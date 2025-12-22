"""
Charts API Routes

Endpoints for chart calculation, reading generation, and reading retrieval.
"""

import os
import json
import asyncio
import requests
import pendulum
import swisseph as swe
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
# Limiter will be set from main app - create placeholder for decorators
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    # Placeholder limiter for decorators - actual limiter set from app.state.limiter at runtime
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    # Dummy limiter if slowapi not available (for development/testing)
    class _DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = _DummyLimiter()
from database import get_db, User, SavedChart
from auth import get_current_user_optional
from natal_chart import (
    NatalChart,
    calculate_numerology, get_chinese_zodiac_and_element,
    calculate_name_numerology,
    TRUE_SIDEREAL_SIGNS
)
from app.services.chart_service import generate_chart_hash, get_quick_highlights
from app.services.llm_prompts import generate_snapshot_reading
from app.services.email_service import send_snapshot_email_via_sendgrid

logger = setup_logger(__name__)

# Create router
router = APIRouter(tags=["charts"])

# Environment variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DEFAULT_SWISS_EPHEMERIS_PATH = os.path.join(BASE_DIR, "swiss_ephemeris")
ADMIN_SECRET_KEY = os.getenv("FRIENDS_AND_FAMILY_KEY")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")

# Reading cache (shared cache module)
from app.core.cache import reading_cache, CACHE_EXPIRY_HOURS


# Pydantic Models
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
    is_full_birth_name: bool = False


class ReadingRequest(BaseModel):
    chart_data: Dict[str, Any]
    unknown_time: bool
    user_inputs: Dict[str, Any]
    chart_image_base64: Optional[str] = None


# Background task functions (preserved exactly)
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
            user_email = user_email.strip() or None
        
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
                from app.services.llm_prompts import get_gemini3_reading
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
            from pdf_generator import generate_pdf_report
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
            from app.services.email_service import send_chart_email_via_sendgrid
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
            from app.services.email_service import send_chart_email_via_sendgrid
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


@router.post("/calculate_chart")
@limiter.limit("200/day")
async def calculate_chart_endpoint(
    request: Request, 
    data: ChartRequest, 
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Calculate a birth chart with all astrological data.
    
    This endpoint calculates the complete birth chart including:
    - Sidereal and tropical placements
    - Aspects and patterns
    - Numerology
    - Chinese zodiac
    - Snapshot reading (if not a transit chart)
    """
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
                name_numerology = None
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
        is_transit_chart = data.full_name.lower() in ["current transits", "transits"]
        if not is_transit_chart:
            logger.info("Generating snapshot reading...")
            try:
                snapshot_reading = await asyncio.wait_for(
                    generate_snapshot_reading(full_response, data.unknown_time),
                    timeout=60.0
                )
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
                full_response["snapshot_reading"] = f"Snapshot reading temporarily unavailable: {str(e)}"
        else:
            full_response["snapshot_reading"] = None
        
        # Automatically generate full reading for FRIENDS_AND_FAMILY_KEY users
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key:
            logger.info(f"FRIENDS_AND_FAMILY_KEY received (length: {len(friends_and_family_key)}, first 3 chars: {friends_and_family_key[:3] if len(friends_and_family_key) >= 3 else friends_and_family_key})")
            logger.info(f"ADMIN_SECRET_KEY configured: {bool(ADMIN_SECRET_KEY)}, length: {len(ADMIN_SECRET_KEY) if ADMIN_SECRET_KEY else 0}")
            if ADMIN_SECRET_KEY and friends_and_family_key == ADMIN_SECRET_KEY:
                if not is_transit_chart and data.user_email:
                    logger.info(f"FRIENDS_AND_FAMILY_KEY detected - automatically generating full reading for {data.full_name}")
                    chart_hash = generate_chart_hash(full_response, data.unknown_time)
                    
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
                    
                    background_tasks.add_task(
                        generate_reading_and_send_email,
                        chart_data=full_response,
                        unknown_time=data.unknown_time,
                        user_inputs=user_inputs
                    )
                    
                    full_response["chart_hash"] = chart_hash
                    full_response["full_reading_queued"] = True
                    logger.info(f"Full reading queued for FRIENDS_AND_FAMILY_KEY user with chart_hash: {chart_hash}")
        
        # Generate chart_hash for all charts
        chart_hash = generate_chart_hash(full_response, data.unknown_time)
        full_response["chart_hash"] = chart_hash
        
        # Auto-save chart if user is logged in
        if current_user:
            try:
                existing_chart = db.query(SavedChart).filter(
                    SavedChart.user_id == current_user.id,
                    SavedChart.chart_name == data.full_name,
                    SavedChart.birth_year == data.year,
                    SavedChart.birth_month == data.month,
                    SavedChart.birth_day == data.day,
                    SavedChart.birth_location == data.location
                ).first()
                
                if not existing_chart:
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
            
        return full_response

    except HTTPException as e:
        logger.error(f"HTTP Exception in /calculate_chart: {e.status_code} - {e.detail}", exc_info=True)
        raise e
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding API request failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Could not connect to the geocoding service.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in /calculate_chart: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred: {type(e).__name__}")


@router.post("/generate_reading")
async def generate_reading_endpoint(
    request: Request, 
    reading_data: ReadingRequest, 
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Queue reading generation and email sending in the background.
    Returns immediately so users can close the browser and still receive their reading via email.
    """
    try:
        user_inputs = reading_data.user_inputs
        chart_name = user_inputs.get('full_name', 'N/A')
        user_email = user_inputs.get('user_email', '')
        
        logger.info(f"Queueing AI reading generation for: {chart_name}")
        
        if not user_email or not user_email.strip():
            raise HTTPException(
                status_code=400, 
                detail="Email address is required. Your reading will be sent to your email when complete."
            )
        
        # Check for FRIENDS_AND_FAMILY_KEY
        friends_and_family_key = request.query_params.get('FRIENDS_AND_FAMILY_KEY')
        if not friends_and_family_key:
            for header_name, header_value in request.headers.items():
                if header_name.lower() == "x-friends-and-family-key":
                    friends_and_family_key = header_value
                    break
        if friends_and_family_key:
            logger.info(f"[generate_reading] FRIENDS_AND_FAMILY_KEY received (length: {len(friends_and_family_key)}, first 3 chars: {friends_and_family_key[:3] if len(friends_and_family_key) >= 3 else friends_and_family_key})")
            logger.info(f"[generate_reading] ADMIN_SECRET_KEY configured: {bool(ADMIN_SECRET_KEY)}, length: {len(ADMIN_SECRET_KEY) if ADMIN_SECRET_KEY else 0}")
        
        from subscription import check_subscription_access
        has_access, reason = check_subscription_access(current_user, db, friends_and_family_key)
        if friends_and_family_key:
            logger.info(f"[generate_reading] Access check result: has_access={has_access}, reason={reason}")
        
        # Log successful admin bypass if used
        if reason == "admin_bypass":
            try:
                from database import AdminBypassLog
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
                error_str = str(log_error)
                if "UniqueViolation" in error_str and "admin_bypass_logs_pkey" in error_str:
                    logger.warning(f"Admin bypass log sequence out of sync. Run fix_admin_logs_sequence.py to resolve. Error: {log_error}")
                    try:
                        db.rollback()
                    except:
                        pass
                else:
                    logger.warning(f"Could not log admin bypass: {log_error}")
        
        chart_hash = generate_chart_hash(reading_data.chart_data, reading_data.unknown_time)
        
        background_tasks.add_task(
            generate_reading_and_send_email,
            chart_data=reading_data.chart_data,
            unknown_time=reading_data.unknown_time,
            user_inputs=user_inputs
        )
        logger.info("Background task queued successfully. User can close browser now.")

        return {
            "status": "processing",
            "message": "Your comprehensive astrology reading is being generated. This thorough analysis takes up to 15 minutes to complete.",
            "instructions": "You can safely close this page - your reading will be sent to your email when ready. If you choose to wait, the reading will also populate on this page when complete.",
            "email": user_email,
            "estimated_time": "up to 15 minutes",
            "chart_hash": chart_hash
        }
    
    except HTTPException:
        raise
    except Exception as e: 
        logger.error(f"Error queueing reading generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_reading/{chart_hash}")
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

