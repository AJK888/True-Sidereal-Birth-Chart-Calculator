# Test Fixtures

This directory contains test fixtures for use in unit and integration tests.

## Available Fixtures

- `sample_chart.json` - Sample birth chart data for testing chart calculations
- `sample_user.json` - Sample user data for testing authentication and user operations
- `sample_reading_request.json` - Sample reading generation request for testing LLM integration

## Usage

### Loading Fixtures in Tests

```python
from app.utils.dev_tools import load_test_fixture

def test_chart_calculation():
    chart_data = load_test_fixture("sample_chart")
    # Use chart_data in your test
```

### Creating New Fixtures

You can create fixtures programmatically:

```python
from app.utils.dev_tools import create_test_fixture

data = {
    "name": "My Test Data",
    "value": 123
}
fixture_path = create_test_fixture("my_fixture", data)
```

Or via the API (development only):

```bash
POST /dev/test-fixture/my_fixture
Content-Type: application/json

{
  "name": "My Test Data",
  "value": 123
}
```

## Best Practices

1. Keep fixtures minimal and focused on specific test scenarios
2. Use descriptive names that indicate the fixture's purpose
3. Include comments in JSON when helpful (though JSON doesn't support comments, consider adding a `_comment` field)
4. Don't include sensitive data in fixtures
5. Update fixtures when data structures change

