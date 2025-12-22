"""
Pytest configuration and shared fixtures.
"""

import pytest
import os
import sys
from typing import Generator
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import app and database
from api import app
from database import Base, get_db


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Generator:
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini3Client for testing."""
    mock_client = Mock()
    mock_client.total_prompt_tokens = 0
    mock_client.total_completion_tokens = 0
    mock_client.total_cost_usd = 0.0
    mock_client.call_count = 0
    
    async def mock_generate(*args, **kwargs):
        mock_client.call_count += 1
        return "Mock LLM response"
    
    mock_client.generate = mock_generate
    mock_client.get_summary = Mock(return_value={
        'total_prompt_tokens': 100,
        'total_completion_tokens': 50,
        'total_tokens': 150,
        'total_cost_usd': 0.0001,
        'call_count': 1
    })
    
    return mock_client


@pytest.fixture
def sample_chart_data():
    """Sample chart data for testing."""
    return {
        "name": "Test User",
        "utc_datetime": "2000-01-01 12:00:00",
        "location": "New York, NY, USA",
        "unknown_time": False,
        "sidereal_major_positions": [
            {"name": "Sun", "position": "10°30' Capricorn", "percentage": 100}
        ],
        "tropical_major_positions": [
            {"name": "Sun", "position": "10°30' Capricorn", "percentage": 100}
        ],
        "sidereal_aspects": [],
        "tropical_aspects": [],
        "numerology_analysis": {
            "life_path_number": 5,
            "day_number": 1
        },
        "chinese_zodiac": "Dragon"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }


@pytest.fixture
def mock_sendgrid():
    """Mock SendGrid client for testing."""
    with patch('app.services.email_service.SendGridAPIClient') as mock_sg:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_sg.return_value.send.return_value = mock_response
        yield mock_sg


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("SENDGRID_API_KEY", "test-sendgrid-key")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "test@example.com")
    monkeypatch.setenv("AI_MODE", "stub")  # Use stub mode for testing

