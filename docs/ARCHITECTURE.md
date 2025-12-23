# Architecture Documentation

**Last Updated:** 2025-01-22

---

## System Architecture

### Overview

The Synthesis Astrology API is a FastAPI-based application providing astrological chart calculations, AI-powered readings, and user management. The application follows a layered architecture with clear separation of concerns.

---

## Architecture Layers

### 1. API Layer (`app/api/v1/`)

**Purpose:** HTTP request handling and routing

**Structure:**
```
app/api/v1/
├── admin/          # Admin endpoints
├── analytics.py    # Analytics endpoints
├── auth.py         # Authentication endpoints
├── batch.py        # Batch processing
├── charts.py       # Chart calculation endpoints
├── data_management.py  # Data export/GDPR
├── dev.py          # Development tools
├── jobs.py         # Job management
├── monitoring.py   # Monitoring endpoints
├── performance.py  # Performance metrics
├── reports.py      # Report generation
├── search.py       # Search endpoints
└── utilities.py    # Utility endpoints
```

**Responsibilities:**
- Request/response handling
- Input validation
- Authentication/authorization
- Error handling
- Response formatting

---

### 2. Service Layer (`app/services/`)

**Purpose:** Business logic and domain operations

**Services:**
- `admin_service.py` - Admin operations
- `analytics_service.py` - Analytics
- `batch_service.py` - Batch processing
- `business_analytics.py` - Business metrics
- `chart_service.py` - Chart formatting
- `composite_service.py` - Composite charts
- `data_export.py` - Data export
- `email_service.py` - Email sending
- `gdpr_service.py` - GDPR compliance
- `job_queue.py` - Background jobs
- `llm_service.py` - LLM interactions
- `localization.py` - Localization
- `revenue_analytics.py` - Revenue tracking
- `search_service.py` - Search functionality
- `synastry_service.py` - Synastry calculations
- `transit_service.py` - Transit calculations
- `user_segmentation.py` - User segmentation

**Responsibilities:**
- Business logic implementation
- Domain operations
- External service integration
- Data transformation

---

### 3. Core Layer (`app/core/`)

**Purpose:** Core functionality and infrastructure

**Components:**
- `advanced_cache.py` - Advanced caching
- `advanced_metrics.py` - Metrics collection
- `analytics.py` - Event tracking
- `api_versioning.py` - API versioning
- `cache.py` - Basic caching
- `cache_enhancements.py` - Cache utilities
- `db_indexes.py` - Database indexes
- `exceptions.py` - Custom exceptions
- `health.py` - Health checks
- `i18n.py` - Internationalization
- `logging_config.py` - Logging configuration
- `monitoring.py` - Basic monitoring
- `performance_middleware.py` - Performance tracking
- `query_optimizer.py` - Query optimization
- `rbac.py` - Role-based access control
- `responses.py` - Response utilities
- `shutdown.py` - Graceful shutdown

**Responsibilities:**
- Infrastructure concerns
- Cross-cutting functionality
- Core utilities
- System-level operations

---

### 4. Data Layer (`database.py`, `app/db/`)

**Purpose:** Data persistence and database operations

**Components:**
- `database.py` - SQLAlchemy models
- `app/db/` - Database utilities and migrations

**Models:**
- `User` - User accounts
- `SavedChart` - Saved charts
- `ChatConversation` - Chat conversations
- `ChatMessage` - Chat messages
- `CreditTransaction` - Credit transactions
- `SubscriptionPayment` - Subscription payments
- `FamousPerson` - Famous people database

**Responsibilities:**
- Data persistence
- Database schema
- Migrations
- Query building

---

### 5. Utilities Layer (`app/utils/`)

**Purpose:** Utility functions and helpers

**Utilities:**
- `api_analytics.py` - API analytics
- `dev_tools.py` - Development tools
- `error_aggregator.py` - Error aggregation
- `export_formatters.py` - Export formatting
- `field_selection.py` - Field selection
- `funnel_analysis.py` - Funnel analysis
- `pagination.py` - Pagination utilities
- `query_analyzer.py` - Query analysis
- `validators.py` - Input validation

**Responsibilities:**
- Helper functions
- Utility operations
- Data processing
- Analysis tools

---

## Request Flow

1. **Request arrives** → FastAPI receives HTTP request
2. **Middleware processing** → Compression, security headers, performance tracking
3. **Authentication** → JWT token validation (if required)
4. **Authorization** → RBAC permission check (if required)
5. **Route handler** → API endpoint processes request
6. **Service layer** → Business logic execution
7. **Data layer** → Database operations
8. **Response** → Formatted response returned

---

## Key Design Patterns

### Dependency Injection

FastAPI's `Depends()` is used throughout for dependency injection:
- Database sessions
- Current user
- Authentication
- Authorization

### Service Pattern

Business logic is encapsulated in service classes:
- Single responsibility
- Reusable
- Testable
- Clear interfaces

### Repository Pattern

Database operations are abstracted through SQLAlchemy:
- Model-based queries
- Relationship handling
- Transaction management

---

## Security Architecture

### Authentication

- JWT tokens for authentication
- Token expiration
- Secure password hashing (bcrypt)

### Authorization

- Role-based access control (RBAC)
- Permission-based authorization
- Admin-only endpoints

### Security Headers

- CORS configuration
- Security headers middleware
- Rate limiting
- Input validation

---

## Performance Architecture

### Caching

- Redis caching (optional)
- In-memory fallback
- Cache invalidation
- Cache statistics

### Query Optimization

- Database indexes
- Query optimization utilities
- N+1 query prevention
- Eager loading

### Monitoring

- Performance middleware
- Query performance tracking
- Cache performance tracking
- Advanced metrics collection

---

## Scalability Architecture

### Horizontal Scaling

- Stateless API design
- Shared cache (Redis)
- Database connection pooling
- Background job queue

### Background Processing

- Job queue system
- Async task processing
- Job status tracking
- Queue statistics

---

## Deployment Architecture

### Production Setup

- FastAPI application
- PostgreSQL database
- Redis cache (optional)
- Background workers (optional)

### Health Monitoring

- Health check endpoints
- Readiness probes
- Liveness probes
- Performance monitoring

---

## Technology Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL (Supabase)
- **ORM:** SQLAlchemy
- **Caching:** Redis (optional)
- **Authentication:** JWT
- **Monitoring:** Custom metrics, performance tracking
- **Testing:** Pytest

---

## Future Considerations

- Microservices architecture (if needed)
- GraphQL API (optional)
- Distributed tracing (OpenTelemetry)
- Advanced monitoring (DataDog, New Relic)
- Message queue (Celery, RQ)

---

**For more details, see individual component documentation.**

