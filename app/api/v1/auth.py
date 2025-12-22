"""
Authentication API Routes

User registration, login, and current user endpoints.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logger
from database import get_db, User
from auth import (
    UserCreate, UserLogin, UserResponse, Token,
    create_user, authenticate_user, get_user_by_email,
    create_access_token, get_current_user
)

logger = setup_logger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["auth"])


# Pydantic Models
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None
    
    @validator('email')
    def validate_email(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('Email is required')
        # Basic email validation
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.strip().lower()
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters')
        return v
    
    @validator('full_name')
    def validate_full_name(cls, v):
        if v is not None:
            if len(v.strip()) == 0:
                return None  # Convert empty string to None
            if len(v) > 255:
                raise ValueError('Full name must be less than 255 characters')
            return v.strip()
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register", response_model=Token)
async def register_endpoint(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, data.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="An account with this email already exists."
            )
        
        # Validate password
        if len(data.password) < 8:
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long."
            )
        
        # Create the user
        user_create = UserCreate(
            email=data.email,
            password=data.password,
            full_name=data.full_name
        )
        user = create_user(db, user_create)
        
        # Create access token (sub must be a string for JWT)
        access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
        
        logger.info(f"New user registered: {user.email}")
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login_endpoint(data: LoginRequest, db: Session = Depends(get_db)):
    """Login and get access token."""
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="This account has been deactivated."
        )
    
    # Create access token (sub must be a string for JWT)
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})
    
    logger.info(f"User logged in: {user.email}")
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse.model_validate(current_user)

