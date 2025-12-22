# Testing Guide

This directory contains tests for the Synthesis Astrology API.

## Test Structure

```
tests/
├── conftest.py           # Shared fixtures and configuration
├── unit/                 # Unit tests (isolated components)
│   ├── test_auth.py     # Authentication endpoint tests
│   └── test_utilities.py # Utility endpoint tests
└── integration/          # Integration tests (full workflows)
    ├── test_charts.py    # Chart calculation tests
    └── test_saved_charts.py # Saved charts CRUD tests
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test file:
```bash
pytest tests/unit/test_auth.py
```

### Run with coverage:
```bash
pytest --cov=app --cov-report=html
```

### Run with verbose output:
```bash
pytest -v
```

## Test Fixtures

The `conftest.py` file provides the following fixtures:

### Database Fixtures
- `db_session` - Fresh database session for each test
- `client` - FastAPI TestClient with database override

### User Fixtures
- `test_user` - Regular test user
- `test_admin_user` - Admin test user
- `auth_headers` - Authentication headers for test user
- `admin_auth_headers` - Authentication headers for admin user

### Mock Fixtures
- `mock_gemini_client` - Mock LLM client
- `mock_sendgrid` - Mock email service
- `mock_env_vars` - Mock environment variables

### Data Fixtures
- `sample_chart_data` - Sample chart data for testing
- `sample_user_data` - Sample user data for testing

## Writing New Tests

### Example Unit Test:
```python
def test_example_endpoint(client, auth_headers):
    """Test an example endpoint."""
    response = client.get(
        "/api/endpoint",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    assert "data" in response.json()
```

### Example Integration Test:
```python
def test_workflow(client, db_session, test_user, auth_headers):
    """Test a complete workflow."""
    # Step 1: Create resource
    create_response = client.post(
        "/api/resource",
        json={"name": "Test"},
        headers=auth_headers
    )
    assert create_response.status_code == 200
    
    # Step 2: Retrieve resource
    resource_id = create_response.json()["id"]
    get_response = client.get(
        f"/api/resource/{resource_id}",
        headers=auth_headers
    )
    assert get_response.status_code == 200
```

## Test Database

Tests use an in-memory SQLite database that is:
- Created fresh for each test
- Dropped after each test
- Isolated from other tests

This ensures:
- Tests don't interfere with each other
- Tests run quickly
- No cleanup needed between tests

## Best Practices

1. **Use fixtures** - Don't create test data manually, use fixtures
2. **Test one thing** - Each test should verify one behavior
3. **Use descriptive names** - Test names should describe what they test
4. **Clean assertions** - Use clear, readable assertions
5. **Mock external services** - Don't call real APIs in tests

## Continuous Integration

Tests should be run:
- Before committing code
- In CI/CD pipeline
- Before deploying to production

## Coverage Goals

- **Unit Tests:** 80%+ coverage for services and utilities
- **Integration Tests:** Cover all critical user workflows
- **Regression Tests:** Ensure calculations and prompts are preserved
