"""
Integration tests for saved charts endpoints.

Tests CRUD operations for saved charts.
"""

import pytest
from fastapi import status


class TestSavedChartsEndpoints:
    """Test saved charts CRUD endpoints."""
    
    def test_save_chart(self, client, db_session, test_user, auth_headers):
        """Test saving a chart."""
        response = client.post(
            "/charts/save",
            json={
                "chart_name": "Test Chart",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_location": "New York, NY, USA",
                "unknown_time": False,
                "chart_data_json": '{"test": "data"}',
                "ai_reading": None
            },
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "message" in data
        assert data["message"] == "Chart saved successfully."
    
    def test_list_charts(self, client, db_session, test_user, auth_headers):
        """Test listing saved charts."""
        # First save a chart
        client.post(
            "/charts/save",
            json={
                "chart_name": "Test Chart",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_location": "New York, NY, USA",
                "unknown_time": False
            },
            headers=auth_headers
        )
        
        # Then list charts
        response = client.get("/charts/list", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "id" in data[0]
        assert "chart_name" in data[0]
    
    def test_get_chart(self, client, db_session, test_user, auth_headers):
        """Test getting a specific chart."""
        # First save a chart
        save_response = client.post(
            "/charts/save",
            json={
                "chart_name": "Test Chart",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_location": "New York, NY, USA",
                "unknown_time": False,
                "chart_data_json": '{"test": "data"}'
            },
            headers=auth_headers
        )
        chart_id = save_response.json()["id"]
        
        # Then get the chart
        response = client.get(f"/charts/{chart_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == chart_id
        assert data["chart_name"] == "Test Chart"
    
    def test_delete_chart(self, client, db_session, test_user, auth_headers):
        """Test deleting a chart."""
        # First save a chart
        save_response = client.post(
            "/charts/save",
            json={
                "chart_name": "Test Chart",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_location": "New York, NY, USA",
                "unknown_time": False
            },
            headers=auth_headers
        )
        chart_id = save_response.json()["id"]
        
        # Then delete the chart
        response = client.delete(f"/charts/{chart_id}", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["message"] == "Chart deleted successfully."
        
        # Verify it's deleted
        get_response = client.get(f"/charts/{chart_id}", headers=auth_headers)
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_save_chart_requires_auth(self, client, db_session):
        """Test saving chart requires authentication."""
        response = client.post(
            "/charts/save",
            json={
                "chart_name": "Test Chart",
                "birth_year": 2000,
                "birth_month": 1,
                "birth_day": 1,
                "birth_hour": 12,
                "birth_minute": 0,
                "birth_location": "New York, NY, USA",
                "unknown_time": False
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

