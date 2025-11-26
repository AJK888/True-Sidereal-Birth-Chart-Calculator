"""
Stripe Integration for Synthesis Astrology

This module handles:
- Credit purchases via Stripe Checkout
- Webhook processing for payment confirmation
- Credit balance management

Setup Required:
1. pip install stripe
2. Set environment variables:
   - STRIPE_SECRET_KEY
   - STRIPE_WEBHOOK_SECRET
   - STRIPE_PRICE_STARTER (price ID for 10 credits)
   - STRIPE_PRICE_EXPLORER (price ID for 30 credits)
   - STRIPE_PRICE_SEEKER (price ID for 100 credits)

3. Create products in Stripe Dashboard:
   - Product: "Synthesis Astrology Credits"
   - Prices:
     - Starter Pack: $4.99 (10 credits)
     - Explorer Pack: $9.99 (30 credits)
     - Seeker Pack: $24.99 (100 credits)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Stripe import - uncomment when ready to integrate
# import stripe

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Price IDs from Stripe Dashboard (set these after creating products)
STRIPE_PRICES = {
    "starter": os.getenv("STRIPE_PRICE_STARTER"),      # 10 credits @ $4.99
    "explorer": os.getenv("STRIPE_PRICE_EXPLORER"),    # 30 credits @ $9.99
    "seeker": os.getenv("STRIPE_PRICE_SEEKER"),        # 100 credits @ $24.99
}

# Credit amounts per package
CREDIT_PACKAGES = {
    "starter": 10,
    "explorer": 30,
    "seeker": 100,
}

# Credit costs per feature
CREDIT_COSTS = {
    "full_reading": 10,
    "chat_message": 1,
    "deep_dive": 5,
}

# Free credits for new users
FREE_CREDITS_NEW_USER = 3

# Frontend URLs for redirects
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://synthesisastrology.com")
SUCCESS_URL = f"{FRONTEND_URL}/payment-success?session_id={{CHECKOUT_SESSION_ID}}"
CANCEL_URL = f"{FRONTEND_URL}/pricing"


# ============================================================================
# Stripe Client Initialization
# ============================================================================

def init_stripe():
    """Initialize Stripe with API key."""
    if not STRIPE_SECRET_KEY:
        logger.warning("STRIPE_SECRET_KEY not set - Stripe integration disabled")
        return False
    
    # Uncomment when ready:
    # stripe.api_key = STRIPE_SECRET_KEY
    logger.info("Stripe initialized successfully")
    return True


# ============================================================================
# Checkout Session Creation
# ============================================================================

async def create_checkout_session(
    user_id: int,
    user_email: str,
    package: str  # "starter", "explorer", or "seeker"
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout session for credit purchase.
    
    Args:
        user_id: The user's database ID
        user_email: User's email for Stripe receipt
        package: Which credit package ("starter", "explorer", "seeker")
    
    Returns:
        Dict with checkout_url and session_id
    """
    if package not in STRIPE_PRICES:
        raise ValueError(f"Invalid package: {package}. Must be one of {list(STRIPE_PRICES.keys())}")
    
    price_id = STRIPE_PRICES[package]
    if not price_id:
        raise ValueError(f"Price ID not configured for package: {package}")
    
    # TODO: Uncomment when ready to integrate
    """
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1,
            }],
            mode="payment",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            customer_email=user_email,
            metadata={
                "user_id": str(user_id),
                "package": package,
                "credits": str(CREDIT_PACKAGES[package]),
            },
            # Optional: Create or use existing Stripe customer
            # customer=stripe_customer_id,
        )
        
        logger.info(f"Created checkout session {session.id} for user {user_id}, package {package}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise
    """
    
    # Placeholder response for development
    return {
        "checkout_url": f"{FRONTEND_URL}/stripe-not-configured",
        "session_id": "placeholder_session_id",
        "message": "Stripe not yet configured"
    }


# ============================================================================
# Webhook Handler
# ============================================================================

async def handle_stripe_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Handle incoming Stripe webhook events.
    
    Args:
        payload: Raw request body
        sig_header: Stripe-Signature header value
    
    Returns:
        Dict with processing result
    """
    if not STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured")
        return {"error": "Webhook secret not configured"}
    
    # TODO: Uncomment when ready to integrate
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        return {"error": "Invalid signature"}
    
    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await handle_successful_payment(session)
        return {"status": "success", "event_type": event["type"]}
    
    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        logger.warning(f"Payment failed: {payment_intent.get('id')}")
        return {"status": "logged", "event_type": event["type"]}
    
    else:
        logger.info(f"Unhandled webhook event type: {event['type']}")
        return {"status": "ignored", "event_type": event["type"]}
    """
    
    return {"message": "Webhook handler not yet implemented"}


async def handle_successful_payment(session: Dict[str, Any]):
    """
    Process a successful payment and add credits to user account.
    
    Args:
        session: Stripe checkout session object
    """
    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id")
    package = metadata.get("package")
    credits_to_add = int(metadata.get("credits", 0))
    
    if not user_id or not credits_to_add:
        logger.error(f"Invalid session metadata: {metadata}")
        return
    
    # TODO: Add credits to user account in database
    """
    from database import get_db, User, CreditTransaction
    
    async with get_db() as db:
        # Get user
        user = await db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            logger.error(f"User not found: {user_id}")
            return
        
        # Add credits
        user.credits += credits_to_add
        
        # Log transaction
        transaction = CreditTransaction(
            user_id=user.id,
            amount=credits_to_add,
            transaction_type="purchase",
            stripe_payment_id=session.get("payment_intent"),
            description=f"Purchased {package} pack ({credits_to_add} credits)"
        )
        db.add(transaction)
        await db.commit()
        
        logger.info(f"Added {credits_to_add} credits to user {user_id}")
    """
    
    logger.info(f"Would add {credits_to_add} credits to user {user_id} (not implemented)")


# ============================================================================
# Credit Management
# ============================================================================

async def get_user_credits(user_id: int) -> int:
    """Get current credit balance for a user."""
    # TODO: Implement database lookup
    """
    from database import get_db, User
    
    async with get_db() as db:
        user = await db.query(User).filter(User.id == user_id).first()
        return user.credits if user else 0
    """
    return 0  # Placeholder


async def use_credits(user_id: int, amount: int, feature: str) -> bool:
    """
    Deduct credits from user account.
    
    Args:
        user_id: User's database ID
        amount: Number of credits to deduct
        feature: What the credits are being used for (for logging)
    
    Returns:
        True if successful, False if insufficient credits
    """
    # TODO: Implement database update
    """
    from database import get_db, User, CreditTransaction
    
    async with get_db() as db:
        user = await db.query(User).filter(User.id == user_id).first()
        if not user or user.credits < amount:
            return False
        
        user.credits -= amount
        
        transaction = CreditTransaction(
            user_id=user.id,
            amount=-amount,
            transaction_type=feature,
            description=f"Used {amount} credits for {feature}"
        )
        db.add(transaction)
        await db.commit()
        
        logger.info(f"User {user_id} used {amount} credits for {feature}")
        return True
    """
    return False  # Placeholder


async def add_free_credits(user_id: int, amount: int = FREE_CREDITS_NEW_USER, reason: str = "new_user"):
    """Add free credits to a user account (for new signups, promotions, etc.)."""
    # TODO: Implement database update
    """
    from database import get_db, User, CreditTransaction
    
    async with get_db() as db:
        user = await db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        user.credits += amount
        
        transaction = CreditTransaction(
            user_id=user.id,
            amount=amount,
            transaction_type="bonus",
            description=f"Free credits: {reason}"
        )
        db.add(transaction)
        await db.commit()
        
        logger.info(f"Added {amount} free credits to user {user_id}: {reason}")
        return True
    """
    logger.info(f"Would add {amount} free credits to user {user_id} (not implemented)")


# ============================================================================
# API Endpoints (to be added to api.py)
# ============================================================================

"""
Add these endpoints to api.py when ready:

from stripe_integration import (
    create_checkout_session,
    handle_stripe_webhook,
    get_user_credits,
    use_credits,
    CREDIT_COSTS,
    CREDIT_PACKAGES
)

@app.get("/api/credits")
async def get_credits(current_user: User = Depends(get_current_user)):
    '''Get current user's credit balance.'''
    credits = await get_user_credits(current_user.id)
    return {
        "credits": credits,
        "costs": CREDIT_COSTS
    }


@app.post("/api/checkout")
async def create_checkout(
    package: str,  # "starter", "explorer", "seeker"
    current_user: User = Depends(get_current_user)
):
    '''Create a Stripe checkout session for credit purchase.'''
    result = await create_checkout_session(
        user_id=current_user.id,
        user_email=current_user.email,
        package=package
    )
    return result


@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    '''Handle Stripe webhook events.'''
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    result = await handle_stripe_webhook(payload, sig_header)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.post("/api/chat")
async def chat_with_chart(
    message: str,
    chart_id: int,
    current_user: User = Depends(get_current_user)
):
    '''Send a chat message about a saved chart (costs 1 credit).'''
    # Check credits
    credits = await get_user_credits(current_user.id)
    if credits < CREDIT_COSTS["chat_message"]:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Insufficient credits",
                "required": CREDIT_COSTS["chat_message"],
                "available": credits
            }
        )
    
    # Process chat (implement your chat logic here)
    # response = await process_chat_message(current_user.id, chart_id, message)
    
    # Deduct credits
    await use_credits(current_user.id, CREDIT_COSTS["chat_message"], "chat_message")
    
    return {"response": "Chat response here", "credits_remaining": credits - 1}


@app.get("/api/pricing")
async def get_pricing():
    '''Get available credit packages and pricing.'''
    return {
        "packages": {
            "starter": {
                "credits": CREDIT_PACKAGES["starter"],
                "price": 4.99,
                "price_display": "$4.99",
                "description": "Perfect for trying out the chat feature"
            },
            "explorer": {
                "credits": CREDIT_PACKAGES["explorer"],
                "price": 9.99,
                "price_display": "$9.99",
                "description": "Best value for regular users",
                "badge": "POPULAR"
            },
            "seeker": {
                "credits": CREDIT_PACKAGES["seeker"],
                "price": 24.99,
                "price_display": "$24.99",
                "description": "For deep exploration and heavy usage"
            }
        },
        "costs": {
            "full_reading": {
                "credits": CREDIT_COSTS["full_reading"],
                "description": "Generate a new comprehensive reading"
            },
            "chat_message": {
                "credits": CREDIT_COSTS["chat_message"],
                "description": "Ask a question about your chart"
            },
            "deep_dive": {
                "credits": CREDIT_COSTS["deep_dive"],
                "description": "In-depth analysis of a specific topic"
            }
        },
        "free_on_signup": FREE_CREDITS_NEW_USER
    }
"""

