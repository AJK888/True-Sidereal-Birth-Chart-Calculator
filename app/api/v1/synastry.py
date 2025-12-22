"""
Synastry API Routes

Comprehensive synastry analysis endpoint (friends & family only).
"""

import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.parse import urlparse, parse_qs

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import get_current_user_optional
from app.services.llm_service import Gemini3Client
from app.services.chart_service import parse_pasted_chart_data
from app.services.llm_prompts import generate_comprehensive_synastry
from app.services.email_service import send_synastry_email

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["synastry"])

# Import centralized configuration
from app.config import GEMINI_API_KEY, ADMIN_SECRET_KEY


# Pydantic Models
class SynastryRequest(BaseModel):
    person1_data: str
    person2_data: str
    user_email: str


@router.post("/synastry")
async def synastry_endpoint(
    request: Request,
    data: SynastryRequest,
    background_tasks: BackgroundTasks,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
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

