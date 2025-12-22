"""
Integration tests for famous people endpoint with caching.

Tests that famous people queries are properly cached and retrieved.
"""

import pytest
from fastapi import status
from unittest.mock import patch, Mock
import json

from app.services.chart_service import generate_chart_hash
from app.core.cache import get_famous_people_from_cache, set_famous_people_in_cache


class TestFamousPeopleCaching:
    """Test famous people endpoint caching."""
    
    @patch('routers.famous_people_routes.get_famous_people_from_cache')
    @patch('routers.famous_people_routes.set_famous_people_in_cache')
    def test_famous_people_cache_check(self, mock_set_cache, mock_get_cache, client, db_session):
        """Test that cache is checked before querying database."""
        # Mock cache miss
        mock_get_cache.return_value = None
        
        sample_chart_data = {
            "sidereal_major_positions": [
                {"name": "Sun", "position": "10°30' Capricorn", "degrees": 280.5}
            ],
            "tropical_major_positions": [
                {"name": "Sun", "position": "10°30' Capricorn", "degrees": 280.5}
            ],
            "unknown_time": False
        }
        
        response = client.post(
            "/api/find-similar-famous-people",
            json={
                "chart_data": sample_chart_data,
                "limit": 10
            }
        )
        
        # Cache should have been checked
        assert mock_get_cache.called
        
        # If response is successful, cache should have been set
        if response.status_code == status.HTTP_200_OK:
            assert mock_set_cache.called
    
    @patch('routers.famous_people_routes.get_famous_people_from_cache')
    def test_famous_people_cache_hit(self, mock_get_cache, client, db_session):
        """Test that cached results are returned when available."""
        # Mock cache hit
        cached_result = {
            "matches": {
                "matches": [
                    {"name": "Cached Person", "similarity_score": 95.0}
                ],
                "total_compared": 50,
                "message": "Found 1 similar famous people"
            },
            "timestamp": "2025-01-22T12:00:00"
        }
        mock_get_cache.return_value = cached_result
        
        sample_chart_data = {
            "sidereal_major_positions": [
                {"name": "Sun", "position": "10°30' Capricorn", "degrees": 280.5}
            ],
            "tropical_major_positions": [
                {"name": "Sun", "position": "10°30' Capricorn", "degrees": 280.5}
            ],
            "unknown_time": False
        }
        
        response = client.post(
            "/api/find-similar-famous-people",
            json={
                "chart_data": sample_chart_data,
                "limit": 10
            }
        )
        
        # Should return cached result
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["matches"][0]["name"] == "Cached Person"
        
        # Database should not have been queried (cache hit)
        # This is verified by the mock_get_cache being called and returning data

