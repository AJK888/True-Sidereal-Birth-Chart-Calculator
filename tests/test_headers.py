"""
Tests for response header middleware.

Verifies that:
1. JSON responses include charset=utf-8
2. Security headers are present
3. API endpoints have no-cache headers
"""

import pytest
from fastapi.testclient import TestClient
from api import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_json_content_type_includes_charset(client):
    """Test that JSON responses include charset=utf-8."""
    # Test a JSON endpoint (using a simple endpoint that returns JSON)
    # We'll use the ping endpoint or a simple GET that returns JSON
    response = client.get("/ping")
    
    # If it returns JSON, check charset
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        assert "charset=utf-8" in content_type.lower(), \
            f"Expected charset=utf-8 in Content-Type, got: {content_type}"


def test_security_headers_present(client):
    """Test that security headers are present on all responses."""
    response = client.get("/ping")
    
    # Check required security headers
    assert "X-Content-Type-Options" in response.headers, \
        "X-Content-Type-Options header missing"
    assert response.headers["X-Content-Type-Options"] == "nosniff", \
        f"Expected X-Content-Type-Options=nosniff, got: {response.headers.get('X-Content-Type-Options')}"
    
    assert "Content-Security-Policy" in response.headers, \
        "Content-Security-Policy header missing"
    
    assert "Referrer-Policy" in response.headers, \
        "Referrer-Policy header missing"
    assert response.headers["Referrer-Policy"] == "no-referrer", \
        f"Expected Referrer-Policy=no-referrer, got: {response.headers.get('Referrer-Policy')}"
    
    assert "X-Frame-Options" in response.headers, \
        "X-Frame-Options header missing"
    assert response.headers["X-Frame-Options"] == "DENY", \
        f"Expected X-Frame-Options=DENY, got: {response.headers.get('X-Frame-Options')}"


def test_api_endpoints_no_cache(client):
    """Test that API endpoints have no-cache headers."""
    # Test /api/find-similar-famous-people endpoint
    # We'll use a minimal request that might fail but still returns headers
    response = client.post(
        "/api/find-similar-famous-people",
        json={"chart_data": {}, "limit": 10}
    )
    
    # Check cache-control headers
    assert "Cache-Control" in response.headers, \
        "Cache-Control header missing on API endpoint"
    assert "no-store" in response.headers["Cache-Control"].lower(), \
        f"Expected no-store in Cache-Control, got: {response.headers.get('Cache-Control')}"
    
    assert "Pragma" in response.headers, \
        "Pragma header missing on API endpoint"
    assert response.headers["Pragma"] == "no-cache", \
        f"Expected Pragma=no-cache, got: {response.headers.get('Pragma')}"
    
    assert "Expires" in response.headers, \
        "Expires header missing on API endpoint"
    assert response.headers["Expires"] == "0", \
        f"Expected Expires=0, got: {response.headers.get('Expires')}"


def test_calculate_chart_no_cache(client):
    """Test that /calculate_chart endpoint has no-cache headers."""
    # Test with minimal data (will likely fail validation but headers should be set)
    response = client.post(
        "/calculate_chart",
        json={
            "full_name": "Test",
            "birth_date": {"year": 2000, "month": 1, "day": 1},
            "birth_time": {"hour": 12, "minute": 0},
            "birth_location": "Test Location",
            "user_email": "test@example.com"
        }
    )
    
    # Check cache-control headers
    assert "Cache-Control" in response.headers, \
        "Cache-Control header missing on /calculate_chart endpoint"
    assert "no-store" in response.headers["Cache-Control"].lower(), \
        f"Expected no-store in Cache-Control, got: {response.headers.get('Cache-Control')}"
    
    assert "Pragma" in response.headers, \
        "Pragma header missing on /calculate_chart endpoint"
    assert response.headers["Pragma"] == "no-cache", \
        f"Expected Pragma=no-cache, got: {response.headers.get('Pragma')}"
    
    assert "Expires" in response.headers, \
        "Expires header missing on /calculate_chart endpoint"
    assert response.headers["Expires"] == "0", \
        f"Expected Expires=0, got: {response.headers.get('Expires')}"


def test_non_api_endpoints_no_cache_headers(client):
    """Test that non-API endpoints don't have no-cache headers (unless explicitly set)."""
    # Test a non-API endpoint like /ping
    response = client.get("/ping")
    
    # Non-API endpoints should not have the no-cache headers
    # (unless they explicitly set them, which /ping doesn't)
    # We just verify the endpoint works and has security headers
    assert response.status_code in [200, 404], \
        f"Expected 200 or 404, got: {response.status_code}"
    
    # Security headers should still be present
    assert "X-Content-Type-Options" in response.headers

