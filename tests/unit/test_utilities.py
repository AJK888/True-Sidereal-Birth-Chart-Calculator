"""
Unit tests for utility endpoints.

Tests health checks, ping, and configuration endpoints.
"""

import pytest
from fastapi import status


class TestUtilityEndpoints:
    """Test utility endpoints."""
    
    def test_ping_endpoint(self, client):
        """Test ping endpoint returns ok."""
        response = client.get("/ping")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "ok"}
    
    def test_ping_head_method(self, client):
        """Test ping endpoint accepts HEAD method."""
        response = client.head("/ping")
        
        assert response.status_code == status.HTTP_200_OK
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns ok."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"message": "ok"}
    
    def test_check_email_config(self, client, mock_env_vars):
        """Test email configuration check endpoint."""
        response = client.get("/check_email_config")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sendgrid_api_key" in data
        assert "sendgrid_from_email" in data
        assert "status" in data
    
    def test_log_clicks_endpoint(self, client):
        """Test log clicks endpoint."""
        response = client.post(
            "/api/log-clicks",
            json={
                "clicks": [
                    {
                        "element": {"tag": "button", "id": "test-btn"},
                        "page": {"url": "https://example.com", "title": "Test"},
                        "timestamp": "2025-01-21T12:00:00Z"
                    }
                ],
                "page": "test-page",
                "timestamp": "2025-01-21T12:00:00Z"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "logged"
        assert data["clicks_received"] == 1

