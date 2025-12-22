"""
Response header middleware for FastAPI.

This module provides middleware to:
1. Normalize JSON Content-Type headers to include charset=utf-8
2. Add security headers to all responses
3. Add no-cache headers to API endpoints
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

NO_STORE = "no-cache, no-store"


class NormalizeJsonContentTypeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure JSON responses include charset=utf-8.
    
    If response Content-Type starts with application/json (or application/problem+json)
    and has no charset param, sets Content-Type to include charset=utf-8,
    preserving any existing parameters if present.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        content_type = response.headers.get("content-type")
        
        if content_type:
            ct_lower = content_type.lower()
            is_json = (
                ct_lower.startswith("application/json") or 
                ct_lower.startswith("application/problem+json")
            )
            has_charset = "charset=" in ct_lower
            
            if is_json and not has_charset:
                response.headers["content-type"] = f"{content_type}; charset=utf-8"
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all API responses.
    
    Adds comprehensive security headers:
    - X-Content-Type-Options: nosniff
    - Content-Security-Policy: default-src 'none'; frame-ancestors 'none' (replaces X-Frame-Options)
    - Referrer-Policy: no-referrer
    - Strict-Transport-Security: max-age=31536000; includeSubDomains (HTTPS only)
    - Permissions-Policy: geolocation=(), microphone=(), camera=()
    
    Note: X-Frame-Options and X-XSS-Protection are deprecated in favor of CSP.
    Uses setdefault so explicit headers from endpoints can override.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Content-Security-Policy", 
            "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # X-Frame-Options and X-XSS-Protection are deprecated - CSP handles this
        
        # HSTS header (only for HTTPS)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains"
            )
        
        # Permissions Policy
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()"
        )
        
        return response


class ApiNoCacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add no-cache headers to API endpoints.
    
    For POST /calculate_chart and POST /api/* paths, sets:
    - Cache-Control: no-cache, no-store
    
    Note: Pragma and Expires headers are deprecated - Cache-Control is sufficient.
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        path = request.url.path
        is_api = (path == "/calculate_chart") or (path.startswith("/api/"))
        
        if is_api:
            response.headers["Cache-Control"] = NO_STORE
            # Pragma and Expires are deprecated - Cache-Control is sufficient
        
        return response

