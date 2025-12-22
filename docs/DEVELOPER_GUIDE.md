# Developer Guide

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or SQLite for development)
- Redis (optional, for caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd True-Sidereal-Birth-Chart
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**
   ```bash
   python -c "from database import init_db; init_db()"
   ```

6. **Run migrations** (if using Alembic)
   ```bash
   alembic upgrade head
   ```

### Running the Server

**Development:**
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**Production:**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

---

## Project Structure

```
True-Sidereal-Birth-Chart/
├── app/
│   ├── api/
│   │   └── v1/          # API v1 routers
│   │       ├── charts.py
│   │       ├── auth.py
│   │       ├── saved_charts.py
│   │       ├── subscriptions.py
│   │       ├── synastry.py
│   │       └── utilities.py
│   ├── core/            # Core functionality
│   │   ├── cache.py      # Caching layer
│   │   ├── config.py     # Configuration
│   │   ├── exceptions.py # Custom exceptions
│   │   ├── logging_config.py
│   │   ├── monitoring.py # Performance monitoring
│   │   └── responses.py  # Response utilities
│   ├── services/         # Business logic services
│   │   ├── chart_service.py
│   │   ├── email_service.py
│   │   ├── llm_service.py
│   │   └── llm_prompts.py
│   └── utils/           # Utility functions
│       ├── metrics.py
│       ├── query_optimization.py
│       └── validators.py
├── database.py          # Database models and setup
├── natal_chart.py       # ⚠️ PRESERVATION ZONE - Chart calculations
├── api.py               # FastAPI app and main entry point
├── tests/               # Test suite
│   ├── unit/           # Unit tests
│   └── integration/    # Integration tests
└── docs/               # Documentation
```

---

## Architecture

### Key Components

1. **API Layer** (`app/api/v1/`)
   - FastAPI routers organized by domain
   - Request/response models
   - Endpoint handlers

2. **Service Layer** (`app/services/`)
   - Business logic
   - External service integrations (LLM, email)
   - Chart formatting and utilities

3. **Core Layer** (`app/core/`)
   - Configuration management
   - Caching
   - Monitoring
   - Exception handling

4. **Data Layer** (`database.py`, `natal_chart.py`)
   - Database models
   - Chart calculations (⚠️ PRESERVATION ZONE)

---

## Development Guidelines

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all functions
- Keep functions focused and small

### Testing

**Run all tests:**
```bash
pytest
```

**Run with coverage:**
```bash
pytest --cov=app --cov-report=html
```

**Run specific test file:**
```bash
pytest tests/unit/test_auth.py
```

### Adding New Endpoints

1. **Create router** (if new domain) or add to existing router
2. **Define request/response models** using Pydantic
3. **Add endpoint handler** with proper documentation
4. **Add tests** (unit and integration)
5. **Update API documentation**

Example:
```python
@router.post("/new-endpoint", tags=["your-tag"])
async def new_endpoint(
    data: YourRequestModel,
    db: Session = Depends(get_db)
) -> YourResponseModel:
    """
    Endpoint description.
    
    More detailed documentation here.
    """
    # Implementation
    return response
```

### Database Migrations

**Create migration:**
```bash
alembic revision --autogenerate -m "Description"
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Rollback:**
```bash
alembic downgrade -1
```

---

## Configuration

### Environment Variables

Key environment variables (see `app/config.py` for full list):

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT secret key
- `GEMINI_API_KEY`: Google Gemini API key
- `SENDGRID_API_KEY`: SendGrid API key
- `REDIS_URL`: Redis connection URL (optional)
- `CACHE_EXPIRY_HOURS`: Cache expiry time (default: 24)

### Configuration Management

All configuration is centralized in `app/config.py`. Use:

```python
from app.config import DATABASE_URL, SECRET_KEY
```

Never use `os.getenv()` directly in application code.

---

## Caching

### Reading Cache

```python
from app.core.cache import get_reading_from_cache, set_reading_in_cache

# Get cached reading
reading = get_reading_from_cache(chart_hash)

# Set reading in cache
set_reading_in_cache(chart_hash, reading_text, chart_name)
```

### Famous People Cache

```python
from app.core.cache import get_famous_people_from_cache, set_famous_people_in_cache

# Get cached matches
matches = get_famous_people_from_cache(cache_key)

# Set matches in cache
set_famous_people_in_cache(cache_key, matches_data)
```

### Cache Backend

- **Redis** (if `REDIS_URL` is set): Distributed caching
- **In-Memory** (fallback): Local process cache

---

## Monitoring

### Metrics Endpoint

```bash
curl http://localhost:8000/api/v1/metrics
```

Returns:
- Health status
- Request counts and durations
- Error rates
- Per-endpoint statistics

### Logging

Logging is configured in `app/core/logging_config.py`. Use:

```python
from app.core.logging_config import setup_logger

logger = setup_logger(__name__)
logger.info("Your log message")
```

---

## ⚠️ Preservation Guidelines

### Critical Files (DO NOT MODIFY)

- `natal_chart.py`: Chart calculation logic
- `app/services/llm_prompts.py`: LLM prompts
- Calculation functions in `natal_chart.py`

### Safe to Modify

- API endpoints (request/response handling)
- Service layer (formatting, utilities)
- Database models (with migrations)
- Configuration
- Tests

### Before Modifying Calculations

1. Read `PRESERVATION_GUIDELINES.md`
2. Create regression tests
3. Verify calculations match expected results
4. Get approval for changes

---

## Deployment

### Render.com

The application is configured for Render.com deployment:

1. **Environment Variables**: Set in Render dashboard
2. **Database**: PostgreSQL instance
3. **Migrations**: Run automatically on startup (see `render.yaml`)

### Local Production Testing

```bash
# Set production environment variables
export DATABASE_URL=postgresql://...
export SECRET_KEY=...
# ... other vars

# Run with production settings
uvicorn api:app --host 0.0.0.0 --port 8000
```

---

## Troubleshooting

### Common Issues

**Database Connection Errors:**
- Check `DATABASE_URL` is correct
- Verify database is running
- Check network connectivity

**Chart Calculation Errors:**
- Verify Swiss Ephemeris files are present
- Check `SWEP_PATH` environment variable
- Verify date/time inputs are valid

**Cache Not Working:**
- Check Redis connection (if using Redis)
- Verify `REDIS_URL` is set correctly
- Check cache expiry settings

**Rate Limiting:**
- Check rate limit headers in response
- Wait for reset time or use different IP
- Contact support for higher limits

---

## Contributing

1. Create feature branch
2. Write tests
3. Implement feature
4. Run tests and linting
5. Submit pull request

---

## Resources

- **API Documentation**: `/docs` (Swagger UI)
- **Alternative Docs**: `/redoc` (ReDoc)
- **Test Coverage**: Run `pytest --cov=app --cov-report=html`
- **Architecture Docs**: See `docs/` directory

---

**Last Updated**: 2025-01-22

