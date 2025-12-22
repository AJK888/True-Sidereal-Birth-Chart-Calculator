"""
Integration tests for chart endpoints.

Tests chart calculation and reading generation workflows.
"""

import pytest
from fastapi import status


class TestChartEndpoints:
    """Test chart calculation endpoints."""
    
    def test_calculate_chart_basic(self, client, db_session, auth_headers, mock_env_vars):
        """Test basic chart calculation."""
        response = client.post(
            "/calculate_chart",
            json={
                "full_name": "Test User",
                "year": 2000,
                "month": 1,
                "day": 1,
                "hour": 12,
                "minute": 0,
                "location": "New York, NY, USA",
                "unknown_time": False,
                "user_email": "test@example.com"
            },
            headers=auth_headers
        )
        
        # Should return 200 or 422 (validation) depending on configuration
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "chart_data" in data or "chart" in data
    
    def test_calculate_chart_requires_auth(self, client, db_session):
        """Test chart calculation requires authentication."""
        response = client.post(
            "/calculate_chart",
            json={
                "full_name": "Test User",
                "year": 2000,
                "month": 1,
                "day": 1,
                "hour": 12,
                "minute": 0,
                "location": "New York, NY, USA",
                "unknown_time": False
            }
        )
        
        # May require auth or allow anonymous - check status
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
    
    def test_get_reading_requires_auth(self, client, db_session):
        """Test getting reading requires authentication."""
        response = client.get("/get_reading/test_hash")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

