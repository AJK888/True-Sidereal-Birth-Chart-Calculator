# Phase 1: Router Migration Plan

**Status:** In Progress  
**Date:** 2025-01-21

## Overview

Breaking up the monolithic `api.py` (2,734 lines) into domain-specific routers following FastAPI best practices.

## Router Structure

```
app/api/v1/
├── __init__.py
├── utilities.py      ✅ Created - Health checks, ping, config
├── charts.py         🔄 In Progress - Chart calculation & readings
├── auth.py           ⏳ Pending - Authentication endpoints
├── saved_charts.py   ⏳ Pending - Saved charts CRUD
├── subscriptions.py  ⏳ Pending - Subscriptions & payments
└── synastry.py       ⏳ Pending - Synastry analysis
```

## Endpoint Mapping

### Utilities Router (`/`)
- `GET /` - Root endpoint
- `GET /ping` - Ping endpoint
- `GET /check_email_config` - Email config check

### Charts Router (`/api/v1/charts` or keep current paths)
- `POST /calculate_chart` - Calculate birth chart
- `POST /generate_reading` - Generate AI reading (background)
- `GET /get_reading/{chart_hash}` - Get reading by hash

### Auth Router (`/auth`)
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user

### Saved Charts Router (`/charts`)
- `POST /charts/save` - Save chart
- `GET /charts/list` - List user's charts
- `GET /charts/{chart_id}` - Get chart by ID
- `DELETE /charts/{chart_id}` - Delete chart

### Subscriptions Router (`/api`)
- `GET /api/subscription/status` - Get subscription status
- `POST /api/reading/checkout` - Create reading checkout
- `POST /api/subscription/checkout` - Create subscription checkout
- `POST /api/webhooks/render-deploy` - Render deploy webhook
- `POST /api/webhooks/stripe` - Stripe webhook

### Utilities Router (`/api`)
- `POST /api/log-clicks` - Log user clicks

### Synastry Router (`/api`)
- `POST /api/synastry` - Synastry analysis (if exists)

## Preservation Requirements

⚠️ **CRITICAL:** All business logic must be preserved exactly:
- All prompt generation logic
- All calculation logic
- All error handling
- All logging
- All background tasks

## Migration Steps

1. ✅ Create directory structure
2. ✅ Create shared dependencies module
3. ✅ Create utilities router
4. 🔄 Create charts router
5. ⏳ Create auth router
6. ⏳ Create saved_charts router
7. ⏳ Create subscriptions router
8. ⏳ Create synastry router
9. ⏳ Update main api.py to include routers
10. ⏳ Test all endpoints
11. ⏳ Remove old endpoint definitions from api.py

## Notes

- Rate limiting: Using shared limiter from `app.core.dependencies`
- Existing routers: `chat_api.py` and `routers/famous_people_routes.py` remain unchanged
- All imports must be preserved exactly
- All business logic must be preserved exactly

