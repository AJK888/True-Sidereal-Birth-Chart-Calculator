"""
Webhook management API endpoints.

Allows users to register, manage, and monitor webhooks for integrations.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import get_current_user
from app.core.webhooks import (
    Webhook, WebhookEvent, generate_webhook_secret,
    create_webhook_payload, deliver_webhook
)

logger = setup_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# Pydantic Models
class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""
    url: HttpUrl = Field(..., description="Webhook URL to receive events")
    events: List[str] = Field(..., description="List of events to subscribe to")
    secret: Optional[str] = Field(None, description="Optional webhook secret for signing")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/webhook",
                "events": ["chart.calculated", "reading.generated"],
                "secret": "optional-secret-key"
            }
        }


class WebhookResponse(BaseModel):
    """Schema for webhook response."""
    id: str
    url: str
    events: List[str]
    active: bool
    created_at: str
    
    class Config:
        from_attributes = True


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = None
    active: Optional[bool] = None
    secret: Optional[str] = None


# In-memory webhook storage (in production, use database)
_webhook_storage: Dict[str, Webhook] = {}


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    data: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new webhook.
    
    Requires authentication. Webhooks will receive events for the authenticated user.
    """
    # Validate events
    valid_events = [e.value for e in WebhookEvent]
    invalid_events = [e for e in data.events if e not in valid_events]
    if invalid_events:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid events: {', '.join(invalid_events)}. Valid events: {', '.join(valid_events)}"
        )
    
    # Generate secret if not provided
    secret = data.secret or generate_webhook_secret()
    
    # Create webhook
    events = [WebhookEvent(e) for e in data.events]
    webhook = Webhook(
        url=str(data.url),
        events=events,
        secret=secret,
        active=True
    )
    
    # Store webhook (in production, save to database)
    import uuid
    webhook.id = str(uuid.uuid4())
    _webhook_storage[webhook.id] = webhook
    
    logger.info(f"Webhook created: {webhook.id} for user {current_user.id}")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        active=webhook.active,
        created_at=webhook.created_at.isoformat()
    )


@router.get("", response_model=List[WebhookResponse])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all webhooks for the authenticated user."""
    # In production, filter by user_id from database
    webhooks = list(_webhook_storage.values())
    
    return [
        WebhookResponse(
            id=wh.id,
            url=wh.url,
            events=[e.value for e in wh.events],
            active=wh.active,
            created_at=wh.created_at.isoformat()
        )
        for wh in webhooks
    ]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific webhook by ID."""
    webhook = _webhook_storage.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        active=webhook.active,
        created_at=webhook.created_at.isoformat()
    )


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    data: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a webhook."""
    webhook = _webhook_storage.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Update webhook
    if data.url is not None:
        webhook.url = str(data.url)
    if data.events is not None:
        valid_events = [e.value for e in WebhookEvent]
        invalid_events = [e for e in data.events if e not in valid_events]
        if invalid_events:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid events: {', '.join(invalid_events)}"
            )
        webhook.events = [WebhookEvent(e) for e in data.events]
    if data.active is not None:
        webhook.active = data.active
    if data.secret is not None:
        webhook.secret = data.secret
    
    logger.info(f"Webhook updated: {webhook_id}")
    
    return WebhookResponse(
        id=webhook.id,
        url=webhook.url,
        events=[e.value for e in webhook.events],
        active=webhook.active,
        created_at=webhook.created_at.isoformat()
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a webhook."""
    webhook = _webhook_storage.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    del _webhook_storage[webhook_id]
    logger.info(f"Webhook deleted: {webhook_id}")
    
    return {"status": "success", "message": "Webhook deleted"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test webhook delivery with a test event."""
    webhook = _webhook_storage.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Create test payload
    from app.core.webhooks import create_webhook_payload, WebhookEvent
    test_payload = create_webhook_payload(
        WebhookEvent.CHART_CALCULATED,
        {"test": True, "message": "This is a test webhook"},
        webhook_id
    )
    
    # Deliver test webhook
    result = await deliver_webhook(webhook, test_payload)
    
    return {
        "status": "success",
        "delivery_result": result
    }

