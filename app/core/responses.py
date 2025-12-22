"""
Standard response formats for the Synthesis Astrology API.

Provides consistent response structures across all endpoints.
"""

from typing import Optional, Dict, Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')


class APIResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    
    status: str = "success"
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    
    status: str = "error"
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


def success_response(
    data: Any = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standard success response.
    
    Args:
        data: Response data
        message: Optional success message
    
    Returns:
        Standardized success response dict
    """
    response = {"status": "success"}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    return response


def error_response(
    error: str,
    detail: Optional[str] = None,
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standard error response.
    
    Args:
        error: Error message
        detail: Optional detailed error information
        code: Optional error code
    
    Returns:
        Standardized error response dict
    """
    response = {
        "status": "error",
        "error": error
    }
    if detail:
        response["detail"] = detail
    if code:
        response["code"] = code
    return response

