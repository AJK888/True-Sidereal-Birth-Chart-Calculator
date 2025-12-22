"""
Webhook management system for integrations.

Provides webhook registration, event publishing, and secure delivery.
"""

import logging
import json
import hmac
import hashlib
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import Redis for webhook queue
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class WebhookEvent(str, Enum):
    """Webhook event types."""
    CHART_CALCULATED = "chart.calculated"
    READING_GENERATED = "reading.generated"
    CHART_SAVED = "chart.saved"
    CHART_DELETED = "chart.deleted"
    USER_REGISTERED = "user.registered"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_CANCELED = "subscription.canceled"
    PAYMENT_RECEIVED = "payment.received"


class WebhookStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class Webhook:
    """Webhook configuration."""
    
    def __init__(
        self,
        url: str,
        events: List[WebhookEvent],
        secret: Optional[str] = None,
        active: bool = True
    ):
        self.url = url
        self.events = events
        self.secret = secret
        self.active = active
        self.created_at = datetime.now()
        self.id = None  # Will be set when stored


def generate_webhook_secret() -> str:
    """Generate a secure webhook secret."""
    import secrets
    return secrets.token_urlsafe(32)


def sign_webhook_payload(payload: Dict[str, Any], secret: str) -> str:
    """
    Sign webhook payload with HMAC SHA256.
    
    Args:
        payload: Webhook payload
        secret: Webhook secret
        
    Returns:
        Signature string
    """
    payload_str = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode('utf-8'),
        payload_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_webhook_signature(
    payload: Dict[str, Any],
    signature: str,
    secret: str
) -> bool:
    """
    Verify webhook signature.
    
    Args:
        payload: Webhook payload
        signature: Received signature
        secret: Webhook secret
        
    Returns:
        True if signature is valid
    """
    expected_signature = sign_webhook_payload(payload, secret)
    return hmac.compare_digest(expected_signature, signature)


def create_webhook_payload(
    event: WebhookEvent,
    data: Dict[str, Any],
    webhook_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create webhook payload.
    
    Args:
        event: Event type
        data: Event data
        webhook_id: Optional webhook ID
        
    Returns:
        Webhook payload dictionary
    """
    return {
        "event": event.value,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "webhook_id": webhook_id
    }


async def deliver_webhook(
    webhook: Webhook,
    payload: Dict[str, Any],
    max_retries: int = 3,
    retry_delay: int = 5
) -> Dict[str, Any]:
    """
    Deliver webhook to URL with retries.
    
    Args:
        webhook: Webhook configuration
        payload: Webhook payload
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries (seconds)
        
    Returns:
        Delivery result dictionary
    """
    if not webhook.active:
        return {
            "status": WebhookStatus.FAILED.value,
            "error": "Webhook is inactive"
        }
    
    # Sign payload if secret is available
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SynthesisAstrology-Webhook/1.0"
    }
    
    if webhook.secret:
        signature = sign_webhook_payload(payload, webhook.secret)
        headers["X-Webhook-Signature"] = f"sha256={signature}"
    
    # Try delivery with retries
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                webhook.url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook delivered successfully: {webhook.url} (attempt {attempt + 1})")
                return {
                    "status": WebhookStatus.SUCCESS.value,
                    "status_code": response.status_code,
                    "attempt": attempt + 1
                }
            else:
                logger.warning(
                    f"Webhook delivery failed: {webhook.url} "
                    f"(status: {response.status_code}, attempt {attempt + 1})"
                )
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook delivery error: {webhook.url} (attempt {attempt + 1}): {e}")
        
        # Wait before retry (except on last attempt)
        if attempt < max_retries:
            import asyncio
            await asyncio.sleep(retry_delay * (attempt + 1))  # Exponential backoff
    
    return {
        "status": WebhookStatus.FAILED.value,
        "error": f"Failed after {max_retries + 1} attempts"
    }


def publish_webhook_event(
    event: WebhookEvent,
    data: Dict[str, Any],
    webhooks: List[Webhook],
    redis_client=None
) -> None:
    """
    Publish webhook event to all registered webhooks.
    
    Args:
        event: Event type
        data: Event data
        webhooks: List of webhook configurations
        redis_client: Optional Redis client for queue
    """
    # Filter webhooks that subscribe to this event
    relevant_webhooks = [
        wh for wh in webhooks
        if event in wh.events and wh.active
    ]
    
    if not relevant_webhooks:
        logger.debug(f"No webhooks registered for event: {event.value}")
        return
    
    # Create payload
    payload = create_webhook_payload(event, data)
    
    # Queue webhook deliveries (use Redis if available, otherwise process immediately)
    if redis_client:
        # Queue in Redis for async processing
        for webhook in relevant_webhooks:
            try:
                queue_data = {
                    "webhook_id": webhook.id,
                    "url": webhook.url,
                    "secret": webhook.secret,
                    "payload": payload
                }
                redis_client.lpush("webhook_queue", json.dumps(queue_data))
                logger.info(f"Queued webhook delivery: {webhook.url}")
            except Exception as e:
                logger.error(f"Error queueing webhook: {e}")
    else:
        # Process immediately (synchronous, not recommended for production)
        import asyncio
        for webhook in relevant_webhooks:
            asyncio.create_task(deliver_webhook(webhook, payload))

