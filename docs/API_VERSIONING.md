# API Versioning Guide

API versioning strategy and migration guide for the Synthesis Astrology API.

---

## Versioning Strategy

### Current Version: v1

All endpoints are currently under `/api/v1/` or root paths that will be versioned in the future.

### Version Format

- **URL Path Versioning:** `/api/v1/`, `/api/v2/`, etc.
- **Header Versioning:** `X-API-Version: v1` (optional, for future)

---

## Version Lifecycle

### Version Introduction

1. **New version created** - New features and breaking changes
2. **Old version maintained** - Backward compatibility for 6-12 months
3. **Deprecation notice** - 3 months before removal
4. **Version removed** - After deprecation period

### Deprecation Policy

- **Minimum 3 months notice** before removing a version
- **Deprecation headers** in responses: `X-API-Deprecated: true`, `X-API-Sunset: 2025-04-22`
- **Documentation updates** with migration guides
- **Email notifications** to API key holders

---

## Current Endpoints (v1)

### Charts
- `POST /calculate_chart` - Calculate birth chart
- `POST /generate_reading` - Generate full reading
- `GET /get_reading` - Get reading status

### Auth
- `POST /auth/register` - Register user
- `POST /auth/login` - Login
- `GET /auth/me` - Get current user

### Saved Charts
- `POST /saved-charts` - Save chart
- `GET /saved-charts` - List charts
- `GET /saved-charts/{id}` - Get chart
- `DELETE /saved-charts/{id}` - Delete chart

### Subscriptions
- `GET /subscriptions/status` - Get subscription status
- `POST /subscriptions/create-checkout` - Create checkout session

### Synastry
- `POST /synastry` - Compare two charts

### Utilities
- `GET /ping` - Health check
- `GET /health` - Comprehensive health check
- `GET /metrics` - Performance metrics

### Webhooks
- `POST /webhooks` - Create webhook
- `GET /webhooks` - List webhooks
- `GET /webhooks/{id}` - Get webhook
- `PATCH /webhooks/{id}` - Update webhook
- `DELETE /webhooks/{id}` - Delete webhook

### API Keys
- `POST /api-keys` - Generate API key
- `GET /api-keys` - List API keys
- `DELETE /api-keys/{id}` - Delete API key

### Batch
- `POST /batch/charts` - Batch chart calculations
- `POST /batch/readings` - Batch reading generation
- `GET /batch/{job_id}` - Get batch job status

### Analytics
- `GET /analytics/usage` - Usage statistics (admin)
- `GET /analytics/user/{id}` - User activity
- `GET /analytics/endpoint/{endpoint}` - Endpoint metrics (admin)

---

## Future Versions (v2)

### Planned Changes

1. **Unified Response Format**
   - All responses wrapped in `{"data": ..., "meta": ...}`
   - Consistent error format

2. **Pagination**
   - Standard pagination for list endpoints
   - Cursor-based pagination

3. **Filtering & Sorting**
   - Query parameters for filtering
   - Standard sorting options

4. **Webhooks v2**
   - Webhook retry policies
   - Webhook event filtering
   - Webhook statistics

5. **Batch Processing v2**
   - Streaming results
   - Partial results
   - Job cancellation

---

## Migration Guide

### From v1 to v2 (When Available)

#### Response Format Changes

**v1:**
```json
{
  "sidereal_major_positions": [...],
  "tropical_major_positions": [...]
}
```

**v2:**
```json
{
  "data": {
    "sidereal_major_positions": [...],
    "tropical_major_positions": [...]
  },
  "meta": {
    "version": "v2",
    "timestamp": "2025-01-22T12:00:00"
  }
}
```

#### Error Format Changes

**v1:**
```json
{
  "detail": "Error message"
}
```

**v2:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Error message",
    "details": {...}
  },
  "meta": {
    "version": "v2",
    "request_id": "req-123"
  }
}
```

---

## Version Detection

### URL Path (Recommended)

```python
# v1
response = requests.get("https://api.synthesisastrology.com/api/v1/charts")

# v2 (future)
response = requests.get("https://api.synthesisastrology.com/api/v2/charts")
```

### Header (Optional)

```python
headers = {"X-API-Version": "v1"}
response = requests.get(url, headers=headers)
```

---

## Backward Compatibility

### Guarantees

- **v1 endpoints remain available** for at least 6 months after v2 release
- **Response formats remain stable** within a version
- **Breaking changes only in new versions**

### Deprecation Timeline

1. **Month 1-3:** v2 released, v1 still supported
2. **Month 4-6:** v1 deprecated, deprecation headers added
3. **Month 7-9:** v1 sunset notice (3 months)
4. **Month 10+:** v1 removed

---

## Best Practices

### 1. Always Specify Version

```python
# Good
base_url = "https://api.synthesisastrology.com/api/v1"

# Bad
base_url = "https://api.synthesisastrology.com"  # No version
```

### 2. Handle Deprecation Warnings

```python
response = requests.get(url)
if response.headers.get("X-API-Deprecated") == "true":
    sunset_date = response.headers.get("X-API-Sunset")
    print(f"API version deprecated. Sunset: {sunset_date}")
    # Plan migration
```

### 3. Test New Versions Early

```python
# Test v2 in staging before production migration
test_url = "https://staging-api.synthesisastrology.com/api/v2/charts"
```

### 4. Monitor Version Usage

```python
# Track which version your app uses
headers = {"X-Client-Version": "my-app/1.0", "X-API-Version": "v1"}
```

---

## Version Support Matrix

| Version | Status | Support Until | Breaking Changes |
|---------|--------|---------------|------------------|
| v1 | ✅ Active | TBD | None |
| v2 | 🔜 Planned | - | Response format, pagination |

---

## Changelog

### v1.0.0 (Current)
- Initial API release
- Chart calculation
- Reading generation
- User authentication
- Saved charts
- Webhooks
- API keys
- Batch processing
- Analytics

---

**Last Updated:** 2025-01-22

