# Best Practices Guide

Development best practices for the Synthesis Astrology API.

---

## Code Organization

### File Structure

- **Keep files under 500 lines** - Split large files into smaller modules
- **One class/function per file** - For complex modules
- **Group related functionality** - Keep related code together

### Naming Conventions

- **Functions:** `snake_case` (e.g., `calculate_chart`)
- **Classes:** `PascalCase` (e.g., `ChartRequest`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `CACHE_EXPIRY_HOURS`)
- **Private functions:** Prefix with `_` (e.g., `_internal_helper`)

---

## Error Handling

### Use Custom Exceptions

```python
from app.core.exceptions import ChartCalculationError, ValidationError

# Good
if not chart_data:
    raise ValidationError("Chart data is required")

# Bad
if not chart_data:
    raise HTTPException(status_code=400, detail="Chart data is required")
```

### Standardize Error Responses

```python
from app.core.responses import error_response

# Good
return error_response(
    error="Invalid input",
    detail="Chart data is required",
    code="VALIDATION_ERROR"
)

# Bad
return {"error": "Invalid input"}  # Inconsistent format
```

### Log Errors Properly

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise
```

---

## Database Operations

### Use Transactions

```python
from database import get_db

db = next(get_db())
try:
    # Multiple operations
    db.add(new_chart)
    db.commit()
except Exception:
    db.rollback()
    raise
finally:
    db.close()
```

### Use Optimized Queries

```python
from app.utils.query_optimization import get_user_charts_optimized

# Good - Uses eager loading
charts = get_user_charts_optimized(db, user_id)

# Bad - N+1 query problem
charts = db.query(SavedChart).filter(SavedChart.user_id == user_id).all()
for chart in charts:
    conversations = chart.conversations  # Separate query per chart
```

### Handle Database Errors

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(new_user)
    db.commit()
except IntegrityError as e:
    db.rollback()
    raise HTTPException(status_code=400, detail="User already exists")
```

---

## Caching

### Use Appropriate Cache Levels

```python
from app.core.advanced_cache import get_from_cache, set_in_cache

# Check cache before expensive operations
cached = get_from_cache(f"chart:{chart_hash}")
if cached:
    return cached

# Compute and cache
result = expensive_operation()
set_in_cache(f"chart:{chart_hash}", result)
return result
```

### Invalidate Cache When Needed

```python
from app.core.advanced_cache import invalidate_cache

# When data changes
invalidate_cache(f"chart:{chart_hash}")
```

---

## Performance

### Use Async for I/O Operations

```python
# Good - Async for external API calls
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# Bad - Blocking I/O
def fetch_data():
    response = requests.get(url)  # Blocks
    return response.json()
```

### Optimize Database Queries

```python
# Good - Single query with joins
charts = db.query(SavedChart)\
    .options(selectinload(SavedChart.conversations))\
    .filter(SavedChart.user_id == user_id)\
    .all()

# Bad - Multiple queries
charts = db.query(SavedChart).filter(SavedChart.user_id == user_id).all()
for chart in charts:
    chart.conversations  # Separate query
```

### Use Background Tasks

```python
from fastapi import BackgroundTasks

# Good - Non-blocking
@router.post("/endpoint")
async def endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(long_running_task)
    return {"status": "processing"}

# Bad - Blocking
@router.post("/endpoint")
async def endpoint():
    long_running_task()  # Blocks response
    return {"status": "done"}
```

---

## Security

### Validate All Input

```python
from app.utils.validators import validate_chart_request_data

# Good
is_valid, error = validate_chart_request_data(data)
if not is_valid:
    raise ValidationError(error)

# Bad
# No validation - security risk
```

### Sanitize User Input

```python
from app.utils.validators import sanitize_string

# Good
clean_name = sanitize_string(user_input, max_length=255)

# Bad
# Direct use of user input - XSS risk
```

### Use Rate Limiting

```python
from app.core.rate_limiting import get_rate_limit_for_endpoint

# Good - Respects user tier
limit = get_rate_limit_for_endpoint(request, "chart_calculations")

# Bad - No rate limiting
```

### Never Log Sensitive Data

```python
# Good
logger.info(f"User {user_id} logged in")

# Bad
logger.info(f"User {user_id} logged in with password {password}")
```

---

## Testing

### Write Unit Tests

```python
import pytest
from app.api.v1.charts import calculate_chart_endpoint

def test_calculate_chart():
    data = {
        "full_name": "Test User",
        "year": 1990,
        "month": 6,
        "day": 15,
        "hour": 14,
        "minute": 30,
        "location": "New York, NY, USA"
    }
    result = await calculate_chart_endpoint(data)
    assert "sidereal_major_positions" in result
```

### Test Error Cases

```python
def test_invalid_date():
    data = {"year": 1990, "month": 13, ...}  # Invalid month
    with pytest.raises(HTTPException) as exc:
        await calculate_chart_endpoint(data)
    assert exc.value.status_code == 400
```

### Use Fixtures

```python
@pytest.fixture
def test_user(db):
    user = User(email="test@example.com", ...)
    db.add(user)
    db.commit()
    return user
```

---

## Documentation

### Document All Endpoints

```python
@router.post(
    "/endpoint",
    summary="Short description",
    description="""
    Detailed description of what the endpoint does.
    
    - Feature 1
    - Feature 2
    """,
    response_description="What the response contains"
)
async def endpoint():
    """Docstring with additional details."""
    pass
```

### Use Type Hints

```python
# Good
def calculate_chart(
    name: str,
    year: int,
    month: int
) -> Dict[str, Any]:
    pass

# Bad
def calculate_chart(name, year, month):
    pass
```

### Add Examples

```python
class ChartRequest(BaseModel):
    """Request model for chart calculation."""
    full_name: str = Field(..., example="John Doe")
    year: int = Field(..., example=1990)
    
    class Config:
        json_schema_extra = {
            "example": {
                "full_name": "John Doe",
                "year": 1990,
                "month": 6,
                "day": 15,
                "hour": 14,
                "minute": 30,
                "location": "New York, NY, USA"
            }
        }
```

---

## Logging

### Use Appropriate Log Levels

```python
# DEBUG - Detailed information for debugging
logger.debug(f"Cache hit for key: {key}")

# INFO - General information
logger.info(f"Chart calculated for: {name}")

# WARNING - Something unexpected but handled
logger.warning(f"Cache miss, falling back to database")

# ERROR - Error that was handled
logger.error(f"Failed to send email: {e}", exc_info=True)

# CRITICAL - Critical error requiring attention
logger.critical(f"Database connection lost")
```

### Include Context

```python
# Good
logger.info(f"Chart calculated", extra={
    "user_id": user_id,
    "chart_hash": chart_hash,
    "duration": duration
})

# Bad
logger.info("Chart calculated")  # No context
```

---

## Configuration

### Use Environment Variables

```python
# Good
from app.config import DATABASE_URL, SECRET_KEY

# Bad
DATABASE_URL = "hardcoded-url"  # Security risk
```

### Validate Configuration

```python
from app.config import validate_config

# On startup
errors = validate_config()
if errors:
    raise RuntimeError(f"Configuration errors: {errors}")
```

---

## API Design

### Use RESTful Conventions

```python
# Good
GET    /saved-charts      # List
POST   /saved-charts      # Create
GET    /saved-charts/123  # Get
PATCH  /saved-charts/123  # Update
DELETE /saved-charts/123  # Delete

# Bad
GET /get_charts
POST /create_chart
GET /chart_by_id
```

### Version Your API

```python
# Good
router = APIRouter(prefix="/api/v1/charts")

# Bad
router = APIRouter(prefix="/charts")  # No versioning
```

### Return Consistent Responses

```python
# Good - Use standard response format
from app.core.responses import success_response

return success_response(
    data={"chart": chart_data},
    message="Chart calculated successfully"
)

# Bad - Inconsistent formats
return {"chart": chart_data}
return {"data": chart_data, "status": "ok"}
```

---

## Monitoring

### Track Important Events

```python
from app.services.analytics_service import track_event

track_event(
    event_type="chart.calculated",
    user_id=user_id,
    metadata={"location": location}
)
```

### Monitor Performance

```python
# Performance middleware automatically tracks:
# - Request duration
# - Error rates
# - Slow requests

# Check metrics
GET /metrics
```

---

## Deployment

### Environment-Specific Configuration

```python
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if ENVIRONMENT == "production":
    # Production settings
    LOG_LEVEL = "WARNING"
else:
    # Development settings
    LOG_LEVEL = "DEBUG"
```

### Health Checks

```python
# Always implement health checks
GET /health      # Comprehensive
GET /health/ready  # Readiness probe
GET /health/live   # Liveness probe
```

### Graceful Shutdown

```python
@app.on_event("shutdown")
async def graceful_shutdown():
    # Close connections
    # Save state
    # Clean up resources
    pass
```

---

## Code Review Checklist

- [ ] Error handling is comprehensive
- [ ] Input validation is present
- [ ] Database queries are optimized
- [ ] Caching is used appropriately
- [ ] Logging is informative
- [ ] Documentation is complete
- [ ] Tests are included
- [ ] Security best practices followed
- [ ] Performance considerations addressed
- [ ] Code follows style guidelines

---

**Last Updated:** 2025-01-22

