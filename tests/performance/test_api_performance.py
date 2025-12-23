"""
Performance Tests

Performance tests for API endpoints.
"""

import pytest
import time
from fastapi.testclient import TestClient

from api import app

client = TestClient(app)


@pytest.mark.performance
def test_chart_calculation_performance():
    """Test chart calculation performance."""
    start = time.time()
    
    response = client.post(
        "/calculate_chart",
        json={
            "birth_year": 1990,
            "birth_month": 1,
            "birth_day": 1,
            "birth_hour": 12,
            "birth_minute": 0,
            "birth_location": "New York, NY"
        }
    )
    
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 2.0  # Should complete in under 2 seconds


@pytest.mark.performance
def test_health_check_performance():
    """Test health check endpoint performance."""
    start = time.time()
    
    response = client.get("/health")
    
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.1  # Should be very fast


@pytest.mark.performance
def test_ping_performance():
    """Test ping endpoint performance."""
    start = time.time()
    
    response = client.get("/ping")
    
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 0.05  # Should be extremely fast

