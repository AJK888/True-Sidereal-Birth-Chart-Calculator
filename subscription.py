"""
Subscription Management for Synthesis Astrology

Handles:
- $28 one-time full reading purchase via Stripe
- Free month of chats after reading purchase
- Monthly $8 subscription for continued chat access
- Subscription status checking
- Webhook processing for subscription events
- Admin bypass logging
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

try:
    import stripe
except ImportError:
    stripe = None
    logging.warning("stripe package not installed. Subscription features will be limited.")

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
# Stripe Price ID for the $28 one-time full reading purchase
# Get this from your Stripe Dashboard: Products > Your Product > Pricing > Price ID (starts with price_)
STRIPE_PRICE_ID_READING = os.getenv("STRIPE_PRICE_ID_READING")
# Stripe Price ID for the monthly $8 subscription (for continued chat access)
STRIPE_PRICE_ID_MONTHLY = os.getenv("STRIPE_PRICE_ID_MONTHLY")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://synthesisastrology.com")
SUCCESS_URL = f"{FRONTEND_URL}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}"
CANCEL_URL = f"{FRONTEND_URL}/pricing"

# Initialize Stripe
if STRIPE_SECRET_KEY and stripe:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("Stripe initialized for subscriptions")
else:
    logger.warning("Stripe not configured - subscription features disabled")


# ============================================================================
# Subscription Status Checking
# ============================================================================

def has_active_subscription(user, db: Session) -> bool:
    """
    Check if user has an active subscription or is in their free month.
    
    Args:
        user: User database object
        db: Database session
    
    Returns:
        True if user has active subscription or is in free month, False otherwise
    """
    if not user:
        return False
    
    # Admin users always have access
    if user.is_admin:
        return True
    
    # Check if user is in their free month (after purchasing a reading)
    if user.has_purchased_reading and user.free_chat_month_end_date:
        if user.free_chat_month_end_date > datetime.utcnow():
            return True
    
    # Check subscription status
    if user.subscription_status == "active":
        # Verify subscription hasn't expired
        if user.subscription_end_date and user.subscription_end_date < datetime.utcnow():
            # Subscription expired, update status
            user.subscription_status = "inactive"
            db.commit()
            return False
        return True
    
    return False


def check_subscription_access(user, db: Session, admin_secret: Optional[str] = None) -> tuple[bool, str]:
    """
    Check if user has subscription access, with optional admin bypass.
    For full readings: requires reading purchase or subscription.
    For chat: requires reading purchase (free month) or active subscription.
    
    Args:
        user: User database object (can be None)
        db: Database session
        admin_secret: Optional admin secret key from URL parameter or header
    
    Returns:
        Tuple of (has_access: bool, reason: str)
    """
    # Check admin bypass FIRST (works even without logged-in user)
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
    if admin_secret and ADMIN_SECRET_KEY and admin_secret == ADMIN_SECRET_KEY:
        # Log admin bypass usage (logging happens in endpoint, not here)
        return True, "admin_bypass"
    
    # If no user, require subscription (admin bypass already checked above)
    if not user:
        return False, "User not authenticated"
    
    # Check subscription or free month
    if has_active_subscription(user, db):
        # Determine the reason
        if user.has_purchased_reading and user.free_chat_month_end_date and user.free_chat_month_end_date > datetime.utcnow():
            return True, "free_month"
        elif user.subscription_status == "active":
            return True, "active_subscription"
    
    return False, "no_subscription"


# ============================================================================
# Stripe Checkout for Reading Purchase
# ============================================================================

def create_reading_checkout(user_id: int, user_email: str) -> Dict[str, Any]:
    """
    Create a Stripe Checkout session for $28 one-time full reading purchase.
    
    Args:
        user_id: User's database ID
        user_email: User's email
    
    Returns:
        Dict with checkout_url and session_id
    """
    if not STRIPE_SECRET_KEY or not stripe:
        raise ValueError("Stripe not configured")
    
    if not STRIPE_PRICE_ID_READING:
        raise ValueError("STRIPE_PRICE_ID_READING not configured")
    
    try:
        # Check if user already has a Stripe customer ID
        from database import User, get_db
        db = next(get_db())
        user = db.query(User).filter(User.id == user_id).first()
        
        customer_id = user.stripe_customer_id if user else None
        
        # Create or retrieve Stripe customer
        if not customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": str(user_id)}
            )
            customer_id = customer.id
            
            # Save customer ID to user
            if user:
                user.stripe_customer_id = customer_id
                db.commit()
        else:
            # Verify customer still exists in Stripe
            try:
                stripe.Customer.retrieve(customer_id)
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist, create new one
                customer = stripe.Customer.create(
                    email=user_email,
                    metadata={"user_id": str(user_id)}
                )
                customer_id = customer.id
                if user:
                    user.stripe_customer_id = customer_id
                    db.commit()
        
        # Create checkout session for one-time reading purchase
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID_READING,
                "quantity": 1,
            }],
            mode="payment",  # One-time payment, not subscription
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={
                "user_id": str(user_id),
                "purchase_type": "reading"
            }
        )
        
        logger.info(f"Created reading purchase checkout session {session.id} for user {user_id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating reading checkout: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating reading checkout: {e}")
        raise


# ============================================================================
# Stripe Checkout for Subscription
# ============================================================================

def create_subscription_checkout(user_id: int, user_email: str) -> Dict[str, Any]:
    """
    Create a Stripe Checkout session for monthly subscription.
    
    Args:
        user_id: User's database ID
        user_email: User's email
    
    Returns:
        Dict with checkout_url and session_id
    """
    if not STRIPE_SECRET_KEY or not stripe:
        raise ValueError("Stripe not configured")
    
    if not STRIPE_PRICE_ID_MONTHLY:
        raise ValueError("STRIPE_PRICE_ID_MONTHLY not configured")
    
    try:
        # Check if user already has a Stripe customer ID
        from database import User, get_db
        db = next(get_db())
        user = db.query(User).filter(User.id == user_id).first()
        
        customer_id = user.stripe_customer_id if user else None
        
        # Create or retrieve Stripe customer
        if not customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": str(user_id)}
            )
            customer_id = customer.id
            
            # Save customer ID to user
            if user:
                user.stripe_customer_id = customer_id
                db.commit()
        else:
            # Verify customer still exists in Stripe
            try:
                stripe.Customer.retrieve(customer_id)
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist, create new one
                customer = stripe.Customer.create(
                    email=user_email,
                    metadata={"user_id": str(user_id)}
                )
                customer_id = customer.id
                if user:
                    user.stripe_customer_id = customer_id
                    db.commit()
        
        # Create checkout session for subscription
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": STRIPE_PRICE_ID_MONTHLY,
                "quantity": 1,
            }],
            mode="subscription",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={
                "user_id": str(user_id),
                "subscription_type": "monthly"
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user_id),
                    "subscription_type": "monthly"
                }
            }
        )
        
        logger.info(f"Created subscription checkout session {session.id} for user {user_id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription checkout: {e}")
        raise
    except Exception as e:
        logger.error(f"Error creating subscription checkout: {e}")
        raise


# ============================================================================
# Webhook Handler for Subscription Events
# ============================================================================

def handle_subscription_webhook(event: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """
    Handle Stripe webhook events related to subscriptions.
    
    Args:
        event: Stripe webhook event
        db: Database session
    
    Returns:
        Dict with processing result
    """
    from database import User, SubscriptionPayment
    
    event_type = event.get("type")
    event_data = event.get("data", {}).get("object", {})
    
    try:
        if event_type == "checkout.session.completed":
            # Checkout completed - could be reading purchase or subscription
            session = event_data
            user_id = int(session.get("metadata", {}).get("user_id", 0))
            purchase_type = session.get("metadata", {}).get("purchase_type", "")
            
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Check if this is a reading purchase (one-time payment)
                    if purchase_type == "reading" and session.get("mode") == "payment":
                        # Reading purchase completed - grant free month of chats
                        user.has_purchased_reading = True
                        user.reading_purchase_date = datetime.utcnow()
                        user.free_chat_month_end_date = datetime.utcnow() + timedelta(days=30)
                        db.commit()
                        logger.info(f"Reading purchase completed for user {user_id}, free month granted until {user.free_chat_month_end_date}")
                    
                    # Check if this is a subscription (recurring payment)
                    subscription_id = session.get("subscription")
                    if subscription_id:
                        user.stripe_subscription_id = subscription_id
                        user.subscription_status = "active"
                        user.subscription_start_date = datetime.utcnow()
                        # Set end date to 1 month from now (will be updated by invoice.paid)
                        user.subscription_end_date = datetime.utcnow() + timedelta(days=30)
                        db.commit()
                        logger.info(f"Activated subscription for user {user_id}")
        
        elif event_type == "customer.subscription.updated":
            # Subscription updated (status change, renewal, etc.)
            subscription = event_data
            subscription_id = subscription.get("id")
            status = subscription.get("status")
            
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if user:
                user.subscription_status = status
                
                # Update dates
                current_period_end = subscription.get("current_period_end")
                if current_period_end:
                    user.subscription_end_date = datetime.fromtimestamp(current_period_end)
                
                db.commit()
                logger.info(f"Updated subscription status for user {user.id}: {status}")
        
        elif event_type == "customer.subscription.deleted":
            # Subscription canceled
            subscription = event_data
            subscription_id = subscription.get("id")
            
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if user:
                user.subscription_status = "canceled"
                db.commit()
                logger.info(f"Canceled subscription for user {user.id}")
        
        elif event_type == "invoice.paid":
            # Monthly payment succeeded
            invoice = event_data
            subscription_id = invoice.get("subscription")
            amount_paid = invoice.get("amount_paid", 0)
            payment_intent = invoice.get("payment_intent")
            
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if user:
                # Update subscription end date
                period_end = invoice.get("period_end")
                if period_end:
                    user.subscription_end_date = datetime.fromtimestamp(period_end)
                    user.subscription_status = "active"
                
                # Record payment
                payment = SubscriptionPayment(
                    user_id=user.id,
                    stripe_payment_intent_id=payment_intent,
                    stripe_invoice_id=invoice.get("id"),
                    amount=amount_paid,
                    currency=invoice.get("currency", "usd"),
                    status="succeeded",
                    payment_date=datetime.fromtimestamp(invoice.get("created", 0)),
                    billing_period_start=datetime.fromtimestamp(invoice.get("period_start", 0)) if invoice.get("period_start") else None,
                    billing_period_end=datetime.fromtimestamp(invoice.get("period_end", 0)) if invoice.get("period_end") else None,
                    description=f"Monthly subscription payment - {invoice.get('description', '')}"
                )
                db.add(payment)
                db.commit()
                logger.info(f"Recorded payment for user {user.id}: ${amount_paid/100:.2f}")
        
        elif event_type == "invoice.payment_failed":
            # Payment failed
            invoice = event_data
            subscription_id = invoice.get("subscription")
            
            user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
            if user:
                user.subscription_status = "past_due"
                db.commit()
                logger.warning(f"Payment failed for user {user.id}")
        
        return {"status": "success", "event_type": event_type}
    
    except Exception as e:
        logger.error(f"Error handling subscription webhook: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "event_type": event_type}

