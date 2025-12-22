"""
Integration tests for transit chart calculations.

Tests transit chart calculation with current location and time.
"""

import pytest
from fastapi import status
from unittest.mock import patch, Mock
import json


class TestTransitChartEndpoints:
    """Test transit chart calculation endpoints."""
    
    @patch('app.api.v1.charts.requests.get')
    def test_calculate_transit_chart_success(self, mock_get, client, db_session, mock_env_vars):
        """Test successful transit chart calculation."""
        # Mock geocoding response
        mock_geocode_response = Mock()
        mock_geocode_response.status_code = 200
        mock_geocode_response.json.return_value = {
            "results": [{
                "geometry": {"lat": 40.7128, "lng": -74.0060},
                "annotations": {"timezone": {"name": "America/New_York"}}
            }]
        }
        
        # Mock timezone lookup
        mock_tz_response = Mock()
        mock_tz_response.status_code = 200
        mock_tz_response.json.return_value = {"timeZone": "America/New_York"}
        
        mock_get.side_effect = [mock_geocode_response, mock_tz_response]
        
        response = client.post(
            "/api/v1/calculate_chart",
            json={
                "full_name": "Current Transits",
                "year": 2025,
                "month": 1,
                "day": 22,
                "hour": 14,
                "minute": 30,
                "location": "New York, NY, USA",
                "unknown_time": False
            }
        )
        
        # Should return 200
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        # Verify transit chart has required fields
        assert "sidereal_major_positions" in data
        assert "tropical_major_positions" in data
        assert "sidereal_aspects" in data
        assert "tropical_aspects" in data
        assert "sidereal_house_cusps" in data
        assert "tropical_house_cusps" in data
        
        # Verify Ascendant exists (required for chart wheel)
        sidereal_positions = data.get("sidereal_major_positions", [])
        tropical_positions = data.get("tropical_major_positions", [])
        
        sidereal_asc = next((p for p in sidereal_positions if p.get("name") == "Ascendant"), None)
        tropical_asc = next((p for p in tropical_positions if p.get("name") == "Ascendant"), None)
        
        assert sidereal_asc is not None, "Sidereal Ascendant must be present"
        assert sidereal_asc.get("degrees") is not None, "Sidereal Ascendant degrees must be present"
        assert tropical_asc is not None, "Tropical Ascendant must be present"
        assert tropical_asc.get("degrees") is not None, "Tropical Ascendant degrees must be present"
    
    @patch('app.api.v1.charts.requests.get')
    def test_transit_chart_invalid_location(self, mock_get, client, db_session, mock_env_vars):
        """Test transit chart with invalid location."""
        # Mock geocoding failure
        mock_get.return_value.status_code = 404
        mock_get.return_value.json.return_value = {"results": []}
        
        response = client.post(
            "/api/v1/calculate_chart",
            json={
                "full_name": "Current Transits",
                "year": 2025,
                "month": 1,
                "day": 22,
                "hour": 14,
                "minute": 30,
                "location": "Invalid Location XYZ",
                "unknown_time": False
            }
        )
        
        # Should return 400 for invalid location
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "location" in response.json()["detail"].lower() or "could not find" in response.json()["detail"].lower()
    
    @patch('app.api.v1.charts.requests.get')
    def test_transit_chart_fallback_location(self, mock_get, client, db_session, mock_env_vars):
        """Test transit chart with fallback to default location."""
        # Mock geocoding to return Boston (fallback)
        mock_geocode_response = Mock()
        mock_geocode_response.status_code = 200
        mock_geocode_response.json.return_value = {
            "results": [{
                "geometry": {"lat": 42.3601, "lng": -71.0589},
                "annotations": {"timezone": {"name": "America/New_York"}}
            }]
        }
        
        mock_tz_response = Mock()
        mock_tz_response.status_code = 200
        mock_tz_response.json.return_value = {"timeZone": "America/New_York"}
        
        mock_get.side_effect = [mock_geocode_response, mock_tz_response]
        
        response = client.post(
            "/api/v1/calculate_chart",
            json={
                "full_name": "Current Transits",
                "year": 2025,
                "month": 1,
                "day": 22,
                "hour": 14,
                "minute": 30,
                "location": "Boston, MA, USA",
                "unknown_time": False
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sidereal_major_positions" in data
        assert len(data.get("sidereal_major_positions", [])) > 0

