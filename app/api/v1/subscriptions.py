"""
Subscriptions API Routes

Subscription status, checkout, and webhook endpoints.
"""

import os
import requests
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import get_current_user
from subscription import handle_subscription_webhook

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["subscriptions"])

# Import centralized configuration
from app.config import STRIPE_WEBHOOK_SECRET, ADMIN_SECRET_KEY, WEBPAGE_DEPLOY_HOOK_URL


@router.get("/subscription/status")
async def get_subscription_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
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
    # ADMIN_SECRET_KEY imported from app.config above
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


@router.post("/reading/checkout")
async def create_reading_checkout_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a Stripe checkout session for $28 one-time full reading purchase."""
    try:
        from subscription import create_reading_checkout
        result = create_reading_checkout(
            user_id=current_user.id,
            user_email=current_user.email
        )
        return result
    except Exception as e:
        logger.error(f"Error creating reading checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscription/checkout")
async def create_subscription_checkout_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Create a Stripe checkout session for $8/month subscription."""
    try:
        from subscription import create_subscription_checkout
        result = create_subscription_checkout(
            user_id=current_user.id,
            user_email=current_user.email
        )
        return result
    except Exception as e:
        logger.error(f"Error creating subscription checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhooks/render-deploy")
async def render_deploy_webhook(request: Request) -> Dict[str, Any]:
    """Handle Render deployment webhook to trigger webpage deployment.
    
    This endpoint is called by Render when the API deployment completes.
    It then triggers a deployment of the webpage service using Render's Deploy Hook URL.
    """
    try:
        # WEBPAGE_DEPLOY_HOOK_URL imported from app.config above
        
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


@router.post("/webhooks/stripe")
async def stripe_webhook_endpoint(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
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

