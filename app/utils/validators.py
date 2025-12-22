"""
Input validation utilities for API endpoints.

Provides validation decorators and helper functions for request validation.
"""

import re
from typing import Any, Callable, Optional
from functools import wraps
from fastapi import HTTPException, status
from pydantic import BaseModel, validator, EmailStr


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_birth_date(year: int, month: int, day: int) -> tuple[bool, Optional[str]]:
    """
    Validate birth date components.
    
    Args:
        year: Birth year
        month: Birth month (1-12)
        day: Birth day (1-31)
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    # Validate year range (reasonable birth years)
    if year < 1900 or year > 2100:
        return False, f"Birth year must be between 1900 and 2100 (got {year})"
    
    # Validate month
    if month < 1 or month > 12:
        return False, f"Birth month must be between 1 and 12 (got {month})"
    
    # Validate day based on month
    days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # Feb has 29 for leap year check
    max_days = days_in_month[month - 1]
    
    if day < 1 or day > max_days:
        return False, f"Birth day must be between 1 and {max_days} for month {month} (got {day})"
    
    # Check for invalid dates (e.g., Feb 30)
    if month == 2 and day > 28:
        # Check if it's a leap year
        is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        if not is_leap and day > 28:
            return False, f"February {day} is not valid in non-leap year {year}"
        if day > 29:
            return False, f"February {day} is not valid"
    
    return True, None


def validate_time(hour: int, minute: int) -> tuple[bool, Optional[str]]:
    """
    Validate time components.
    
    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if hour < 0 or hour > 23:
        return False, f"Hour must be between 0 and 23 (got {hour})"
    
    if minute < 0 or minute > 59:
        return False, f"Minute must be between 0 and 59 (got {minute})"
    
    return True, None


def validate_location(location: str) -> tuple[bool, Optional[str]]:
    """
    Validate location string.
    
    Args:
        location: Location string
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if not location or not isinstance(location, str):
        return False, "Location is required and must be a string"
    
    if len(location.strip()) < 2:
        return False, "Location must be at least 2 characters"
    
    if len(location) > 500:
        return False, "Location must be less than 500 characters"
    
    return True, None


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input by trimming whitespace and optionally limiting length.
    
    Args:
        value: String to sanitize
        max_length: Optional maximum length
        
    Returns:
        Sanitized string
    """
    if not isinstance(value, str):
        return str(value) if value else ""
    
    sanitized = value.strip()
    
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def validate_chart_request_data(data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate chart request data.
    
    Args:
        data: Chart request data dictionary
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    # Validate required fields
    required_fields = ['year', 'month', 'day', 'hour', 'minute', 'location']
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate birth date
    is_valid, error = validate_birth_date(
        data['year'],
        data['month'],
        data['day']
    )
    if not is_valid:
        return False, error
    
    # Validate time
    is_valid, error = validate_time(data['hour'], data['minute'])
    if not is_valid:
        return False, error
    
    # Validate location
    is_valid, error = validate_location(data['location'])
    if not is_valid:
        return False, error
    
    # Validate full_name if provided
    if 'full_name' in data and data['full_name']:
        full_name = str(data['full_name'])
        if len(full_name.strip()) < 1:
            return False, "Full name cannot be empty"
        if len(full_name) > 255:
            return False, "Full name must be less than 255 characters"
    
    return True, None

