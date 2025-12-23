"""
Webhook Enhancements

Enhanced webhook functionality with retry, signing, and validation.
"""

import logging
import hmac
import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.core.logging_config import setup_logger
from app.core.retry import retry, RetryConfig
from app.core.circuit_breaker_enhanced import get_circuit_breaker

logger = setup_logger(__name__)


class WebhookSigner:
    """Webhook signature generator and verifier."""
    
    @staticmethod
    def generate_signature(
        payload: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> str:
        """Generate webhook signature."""
        if algorithm == "sha256":
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha1":
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha1
            ).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    @staticmethod
    def verify_signature(
        payload: str,
        signature: str,
        secret: str,
        algorithm: str = "sha256"
    ) -> bool:
        """Verify webhook signature."""
        expected_signature = WebhookSigner.generate_signature(
            payload, secret, algorithm
        )
        return hmac.compare_digest(expected_signature, signature)


class WebhookDelivery:
    """Represents a webhook delivery attempt."""
    
    def __init__(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        secret: Optional[str] = None
    ):
        self.url = url
        self.payload = payload
        self.headers = headers or {}
        self.secret = secret
        self.attempts = 0
        self.last_attempt = None
        self.success = False
        self.response_code = None
        self.response_body = None
        self.error = None
    
    def add_signature(self):
        """Add signature to headers."""
        if not self.secret:
            return
        
        payload_str = json.dumps(self.payload, sort_keys=True)
        signature = WebhookSigner.generate_signature(payload_str, self.secret)
        self.headers["X-Webhook-Signature"] = f"sha256={signature}"
        self.headers["X-Webhook-Timestamp"] = str(int(time.time()))


class WebhookClient:
    """Enhanced webhook client with retry and circuit breaker."""
    
    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._circuit_breakers: Dict[str, Any] = {}
    
    def _get_circuit_breaker(self, url: str) -> Any:
        """Get or create circuit breaker for URL."""
        domain = urlparse(url).netloc
        if domain not in self._circuit_breakers:
            self._circuit_breakers[domain] = get_circuit_breaker(
                f"webhook_{domain}",
                failure_threshold=5,
                recovery_timeout=60
            )
        return self._circuit_breakers[domain]
    
    @retry(config=RetryConfig(max_attempts=3, initial_delay=1.0))
    async def deliver(
        self,
        delivery: WebhookDelivery
    ) -> bool:
        """Deliver webhook with retry logic."""
        delivery.attempts += 1
        delivery.last_attempt = datetime.utcnow()
        
        # Add signature if secret provided
        delivery.add_signature()
        
        # Get circuit breaker
        cb = self._get_circuit_breaker(delivery.url)
        
        try:
            # Call with circuit breaker protection
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await cb.call(
                    client.post,
                    delivery.url,
                    json=delivery.payload,
                    headers=delivery.headers
                )
                
                delivery.response_code = response.status_code
                delivery.response_body = response.text
                
                if 200 <= response.status_code < 300:
                    delivery.success = True
                    logger.info(
                        f"Webhook delivered successfully to {delivery.url} "
                        f"(attempt {delivery.attempts})"
                    )
                    return True
                else:
                    delivery.error = f"HTTP {response.status_code}"
                    logger.warning(
                        f"Webhook delivery failed to {delivery.url}: "
                        f"HTTP {response.status_code}"
                    )
                    return False
        except Exception as e:
            delivery.error = str(e)
            logger.error(
                f"Webhook delivery error to {delivery.url}: {str(e)}"
            )
            raise
    
    async def deliver_with_fallback(
        self,
        delivery: WebhookDelivery,
        fallback_urls: List[str]
    ) -> bool:
        """Deliver webhook with fallback URLs."""
        # Try primary URL
        try:
            if await self.deliver(delivery):
                return True
        except Exception as e:
            logger.warning(f"Primary webhook failed: {str(e)}")
        
        # Try fallback URLs
        for fallback_url in fallback_urls:
            delivery.url = fallback_url
            try:
                if await self.deliver(delivery):
                    logger.info(f"Webhook delivered via fallback: {fallback_url}")
                    return True
            except Exception as e:
                logger.warning(f"Fallback webhook failed: {str(e)}")
                continue
        
        return False


# Global webhook client instance
webhook_client = WebhookClient()

