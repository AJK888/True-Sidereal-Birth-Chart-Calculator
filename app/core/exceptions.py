"""
Custom exceptions for the Synthesis Astrology API.

Provides standardized exception classes for consistent error handling.
"""

from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class SynthesisAPIException(HTTPException):
    """Base exception for Synthesis Astrology API errors."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.context = context or {}
        self.error_code = error_code


class ChartCalculationError(SynthesisAPIException):
    """Raised when chart calculation fails."""
    
    def __init__(
        self,
        detail: str = "Failed to calculate birth chart",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context,
            error_code=error_code or "CHART_CALCULATION_ERROR"
        )


class GeocodingError(SynthesisAPIException):
    """Raised when geocoding fails."""
    
    def __init__(
        self,
        detail: str = "Could not find location data",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            context=context,
            error_code=error_code or "GEOCODING_ERROR"
        )


class ReadingGenerationError(SynthesisAPIException):
    """Raised when reading generation fails."""
    
    def __init__(
        self,
        detail: str = "Failed to generate reading",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context,
            error_code=error_code or "READING_GENERATION_ERROR"
        )


class EmailError(SynthesisAPIException):
    """Raised when email sending fails."""
    
    def __init__(
        self,
        detail: str = "Failed to send email",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context,
            error_code=error_code or "EMAIL_ERROR"
        )


class LLMError(SynthesisAPIException):
    """Raised when LLM API call fails."""
    
    def __init__(
        self,
        detail: str = "LLM service error",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            context=context,
            error_code=error_code or "LLM_ERROR"
        )


class ValidationError(SynthesisAPIException):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        detail: str = "Invalid input",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        field: Optional[str] = None
    ):
        if context is None:
            context = {}
        if field:
            context["field"] = field
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            context=context,
            error_code=error_code or "VALIDATION_ERROR"
        )


class AuthenticationError(SynthesisAPIException):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        detail: str = "Authentication failed",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            context=context,
            error_code=error_code or "AUTHENTICATION_ERROR"
        )


class AuthorizationError(SynthesisAPIException):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        detail: str = "Not authorized",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            context=context,
            error_code=error_code or "AUTHORIZATION_ERROR"
        )


class NotFoundError(SynthesisAPIException):
    """Raised when a resource is not found."""
    
    def __init__(
        self,
        detail: str = "Resource not found",
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        if context is None:
            context = {}
        if resource_type:
            context["resource_type"] = resource_type
        if resource_id:
            context["resource_id"] = resource_id
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            context=context,
            error_code=error_code or "NOT_FOUND_ERROR"
        )

