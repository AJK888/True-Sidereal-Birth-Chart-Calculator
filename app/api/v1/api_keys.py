"""
API key management endpoints.

Allows users to generate and manage API keys for programmatic access.
"""

import logging
import secrets
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text

from app.core.logging_config import setup_logger
from database import get_db, User
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
from auth import get_current_user

logger = setup_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


# API Key Model (in-memory for now, should be in database)
class APIKey(Base):
    """API Key model."""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(20), nullable=False)  # First 8 chars for display
    name = Column(String(255), nullable=True)  # User-friendly name
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    
    # Relationship
    user = None  # Will be set via relationship


# In-memory storage (in production, use database)
_api_key_storage: Dict[str, Dict[str, Any]] = {}


# Pydantic Models
class APIKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: Optional[str] = Field(None, description="User-friendly name for the API key")
    expires_days: Optional[int] = Field(None, description="Number of days until expiration (None for no expiration)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production API Key",
                "expires_days": 365
            }
        }


class APIKeyResponse(BaseModel):
    """Schema for API key response."""
    id: str
    key: str  # Only shown on creation
    key_prefix: str
    name: Optional[str]
    created_at: str
    expires_at: Optional[str]
    last_used: Optional[str]
    usage_count: int
    is_active: bool
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Schema for API key list response (without full key)."""
    id: str
    key_prefix: str
    name: Optional[str]
    created_at: str
    expires_at: Optional[str]
    last_used: Optional[str]
    usage_count: int
    is_active: bool


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_hash)
    """
    # Generate secure random key
    full_key = f"sk_{secrets.token_urlsafe(32)}"
    
    # Hash the key for storage
    key_hash = hashlib.sha256(full_key.encode('utf-8')).hexdigest()
    
    return full_key, key_hash


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against stored hash.
    
    Args:
        api_key: API key to verify
        stored_hash: Stored hash
        
    Returns:
        True if key matches
    """
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    return key_hash == stored_hash


@router.post("", response_model=APIKeyResponse)
async def create_api_key(
    data: APIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a new API key.
    
    The full key is only shown once on creation. Store it securely.
    """
    # Generate API key
    full_key, key_hash = generate_api_key()
    key_prefix = full_key[:12]  # First 12 characters for display
    
    # Calculate expiration
    expires_at = None
    if data.expires_days:
        expires_at = datetime.utcnow() + timedelta(days=data.expires_days)
    
    # Store API key (in production, save to database)
    import uuid
    key_id = str(uuid.uuid4())
    _api_key_storage[key_id] = {
        "id": key_id,
        "user_id": current_user.id,
        "key_hash": key_hash,
        "key_prefix": key_prefix,
        "name": data.name,
        "created_at": datetime.utcnow(),
        "expires_at": expires_at,
        "is_active": True,
        "usage_count": 0,
        "last_used": None
    }
    
    logger.info(f"API key created: {key_prefix}... for user {current_user.id}")
    
    return APIKeyResponse(
        id=key_id,
        key=full_key,  # Only shown on creation
        key_prefix=key_prefix,
        name=data.name,
        created_at=_api_key_storage[key_id]["created_at"].isoformat(),
        expires_at=expires_at.isoformat() if expires_at else None,
        last_used=None,
        usage_count=0,
        is_active=True
    )


@router.get("", response_model=List[APIKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys for the authenticated user."""
    # Filter by user_id (in production, query database)
    user_keys = [
        key for key in _api_key_storage.values()
        if key["user_id"] == current_user.id
    ]
    
    return [
        APIKeyListResponse(
            id=key["id"],
            key_prefix=key["key_prefix"],
            name=key["name"],
            created_at=key["created_at"].isoformat(),
            expires_at=key["expires_at"].isoformat() if key["expires_at"] else None,
            last_used=key["last_used"].isoformat() if key["last_used"] else None,
            usage_count=key["usage_count"],
            is_active=key["is_active"]
        )
        for key in user_keys
    ]


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an API key."""
    key_data = _api_key_storage.get(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if key_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    del _api_key_storage[key_id]
    logger.info(f"API key deleted: {key_id}")
    
    return {"status": "success", "message": "API key deleted"}


@router.patch("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revoke an API key (disable it without deleting)."""
    key_data = _api_key_storage.get(key_id)
    if not key_data:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if key_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    key_data["is_active"] = False
    logger.info(f"API key revoked: {key_id}")
    
    return {"status": "success", "message": "API key revoked"}


def get_user_from_api_key(api_key: str, db: Session) -> Optional[User]:
    """
    Get user from API key.
    
    Args:
        api_key: API key string
        db: Database session
        
    Returns:
        User object or None if invalid
    """
    if not api_key or not api_key.startswith("sk_"):
        return None
    
    # Hash the provided key
    key_hash = hashlib.sha256(api_key.encode('utf-8')).hexdigest()
    
    # Find matching key (in production, query database)
    for key_data in _api_key_storage.values():
        if key_data["key_hash"] == key_hash:
            # Check if active and not expired
            if not key_data["is_active"]:
                return None
            
            if key_data["expires_at"] and datetime.utcnow() > key_data["expires_at"]:
                return None
            
            # Update usage stats
            key_data["usage_count"] += 1
            key_data["last_used"] = datetime.utcnow()
            
            # Get user from database
            user = db.query(User).filter(User.id == key_data["user_id"]).first()
            return user
    
    return None

