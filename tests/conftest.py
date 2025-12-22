"""
Pytest configuration and shared fixtures for testing.

This module provides common test fixtures and configuration
for all test modules.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import app and database
from api import app
from database import Base, get_db, User
from auth import create_access_token, get_password_hash


# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Create test session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.
    Database is created and dropped for each test.
    """
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    # Create session
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with database dependency override.
    """
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
def test_user(db_session):
    """
    Create a test user for authentication tests.
    """
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
        full_name="Test User",
        is_active=True,
        is_admin=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_user(db_session):
    """
    Create a test admin user.
    """
    user = User(
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword123"),
        full_name="Admin User",
        is_active=True,
        is_admin=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """
    Create authentication headers for a test user.
    """
    access_token = create_access_token(data={"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user):
    """
    Create authentication headers for an admin user.
    """
    access_token = create_access_token(data={"sub": str(test_admin_user.id), "email": test_admin_user.email})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def mock_gemini_client():
    """Mock Gemini3Client for testing."""
    from unittest.mock import Mock
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
    from unittest.mock import Mock, patch
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
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-testing")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
