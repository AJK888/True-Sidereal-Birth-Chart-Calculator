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
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class ChartCalculationError(SynthesisAPIException):
    """Raised when chart calculation fails."""
    
    def __init__(self, detail: str = "Failed to calculate birth chart"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class GeocodingError(SynthesisAPIException):
    """Raised when geocoding fails."""
    
    def __init__(self, detail: str = "Could not find location data"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class ReadingGenerationError(SynthesisAPIException):
    """Raised when reading generation fails."""
    
    def __init__(self, detail: str = "Failed to generate reading"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class EmailError(SynthesisAPIException):
    """Raised when email sending fails."""
    
    def __init__(self, detail: str = "Failed to send email"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class LLMError(SynthesisAPIException):
    """Raised when LLM API call fails."""
    
    def __init__(self, detail: str = "LLM service error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )


class ValidationError(SynthesisAPIException):
    """Raised when input validation fails."""
    
    def __init__(self, detail: str = "Invalid input"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class AuthenticationError(SynthesisAPIException):
    """Raised when authentication fails."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )


class AuthorizationError(SynthesisAPIException):
    """Raised when authorization fails."""
    
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class NotFoundError(SynthesisAPIException):
    """Raised when a resource is not found."""
    
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

