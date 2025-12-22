# Test Suite

This directory contains the test suite for the Synthesis Astrology backend.

## Structure

- `conftest.py` - Shared pytest fixtures and configuration
- `unit/` - Unit tests
  - `test_services.py` - Service module tests
  - `test_calculations_preserved.py` - Calculation regression tests
  - `test_prompts_preserved.py` - Prompt regression tests

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_services.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run with verbose output
pytest -v
```

## Test Categories

### Unit Tests (`test_services.py`)
- Test individual service functions
- Mock external dependencies (Gemini API, SendGrid)
- Verify function behavior and return values

### Regression Tests (`test_calculations_preserved.py`)
- ⚠️ **CRITICAL**: Verify calculations remain unchanged
- Test chart calculation structure
- Verify numerology and Chinese zodiac calculations
- Ensure house calculations work correctly

### Prompt Tests (`test_prompts_preserved.py`)
- ⚠️ **CRITICAL**: Verify prompts remain unchanged
- Test prompt function signatures
- Verify functions are callable
- Ensure prompt structure is preserved

## Important Notes

- **Preservation Tests**: The calculation and prompt tests are critical for ensuring no breaking changes
- **Mocking**: External APIs (Gemini, SendGrid) are mocked to avoid API costs during testing
- **Database**: Tests use an in-memory SQLite database that's created/destroyed per test
- **Environment**: Tests use stub mode for AI (`AI_MODE=stub`) to avoid API calls

## Adding New Tests

When adding new functionality:
1. Add unit tests to `test_services.py`
2. If modifying calculations, add regression tests to `test_calculations_preserved.py`
3. If modifying prompts, add tests to `test_prompts_preserved.py`
4. Update this README if adding new test categories

