"""
Response Compression Middleware

Compresses HTTP responses using gzip or brotli for better performance.
"""

import logging
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
import gzip
import io

from app.core.logging_config import setup_logger

logger = setup_logger(__name__)


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware to compress HTTP responses."""
    
    MIN_SIZE = 1024  # Only compress responses larger than 1KB
    COMPRESSIBLE_TYPES = {
        "application/json",
        "application/javascript",
        "text/html",
        "text/css",
        "text/plain",
        "text/xml",
        "application/xml",
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request and compress response if applicable."""
        response = await call_next(request)
        
        # Check if compression is requested
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response
        
        # Check if response should be compressed
        if not self._should_compress(response):
            return response
        
        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Compress response
        compressed_body = gzip.compress(response_body, compresslevel=6)
        
        # Create new response with compressed body
        compressed_response = Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )
        compressed_response.headers["Content-Encoding"] = "gzip"
        compressed_response.headers["Content-Length"] = str(len(compressed_body))
        compressed_response.headers["Vary"] = "Accept-Encoding"
        
        return compressed_response
    
    def _should_compress(self, response: Response) -> bool:
        """Check if response should be compressed."""
        # Check content type
        content_type = response.headers.get("content-type", "")
        if not any(ct in content_type for ct in self.COMPRESSIBLE_TYPES):
            return False
        
        # Check content length
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) < self.MIN_SIZE:
                    return False
            except ValueError:
                pass
        
        # Don't compress if already compressed
        if response.headers.get("content-encoding"):
            return False
        
        return True

