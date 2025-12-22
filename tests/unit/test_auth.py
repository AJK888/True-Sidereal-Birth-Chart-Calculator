"""
Unit tests for authentication endpoints.

Tests user registration, login, and current user retrieval.
"""

import pytest
from fastapi import status
from app.api.v1.auth import RegisterRequest, LoginRequest


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_register_new_user(self, client, db_session):
        """Test registering a new user."""
        response = client.post(
            "/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "full_name": "New User"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
    
    def test_register_duplicate_email(self, client, db_session, test_user):
        """Test registering with duplicate email fails."""
        response = client.post(
            "/auth/register",
            json={
                "email": test_user.email,
                "password": "password123",
                "full_name": "Duplicate User"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"].lower()
    
    def test_register_short_password(self, client, db_session):
        """Test registering with short password fails."""
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "short",
                "full_name": "User"
            }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "8 characters" in response.json()["detail"]
    
    def test_login_success(self, client, db_session, test_user):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_user.email
    
    def test_login_invalid_credentials(self, client, db_session, test_user):
        """Test login with invalid credentials fails."""
        response = client.post(
            "/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.json()["detail"].lower()
    
    def test_get_current_user(self, client, db_session, test_user, auth_headers):
        """Test getting current authenticated user."""
        response = client.get(
            "/auth/me",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
    
    def test_get_current_user_unauthorized(self, client, db_session):
        """Test getting current user without auth fails."""
        response = client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

