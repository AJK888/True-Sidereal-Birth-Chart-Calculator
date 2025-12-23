# API Examples

Complete examples for using the Synthesis Astrology API.

---

## Authentication

### Register a New User

```bash
curl -X POST https://api.synthesisastrology.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123",
    "full_name": "John Doe"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "created_at": "2025-01-22T12:00:00",
    "is_active": true
  }
}
```

### Login

```bash
curl -X POST https://api.synthesisastrology.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe",
    "created_at": "2025-01-22T12:00:00",
    "is_active": true
  }
}
```

### Using Authentication Token

```bash
curl -X GET https://api.synthesisastrology.com/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Chart Calculation

### Calculate a Birth Chart

```bash
curl -X POST https://api.synthesisastrology.com/calculate_chart \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Doe",
    "year": 1990,
    "month": 6,
    "day": 15,
    "hour": 14,
    "minute": 30,
    "location": "New York, NY, USA",
    "unknown_time": false
  }'
```

**Response:**
```json
{
  "sidereal_major_positions": [...],
  "tropical_major_positions": [...],
  "sidereal_aspects": [...],
  "tropical_aspects": [...],
  "numerology": {
    "life_path_number": 5,
    "day_number": 6,
    "lucky_number": 3
  },
  "chinese_zodiac": {
    "animal": "Horse",
    "element": "Metal"
  },
  "snapshot_reading": "Your chart reveals..."
}
```

### Calculate Current Transits

```bash
curl -X POST https://api.synthesisastrology.com/calculate_chart \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "Current Transits",
    "year": 2025,
    "month": 1,
    "day": 22,
    "hour": 12,
    "minute": 0,
    "location": "New York, NY, USA"
  }'
```

---

## Reading Generation

### Generate a Full Reading

```bash
curl -X POST https://api.synthesisastrology.com/generate_reading \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "chart_data": {
      "sidereal_major_positions": [...],
      "tropical_major_positions": [...]
    },
    "unknown_time": false,
    "user_email": "user@example.com"
  }'
```

**Response:**
```json
{
  "status": "processing",
  "message": "Your comprehensive astrology reading is being generated...",
  "chart_hash": "abc123..."
}
```

### Get Reading Status

```bash
curl -X GET "https://api.synthesisastrology.com/get_reading?chart_hash=abc123" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (when ready):**
```json
{
  "status": "completed",
  "reading": "Your comprehensive astrology reading...",
  "chart_name": "John Doe"
}
```

---

## Saved Charts

### Save a Chart

```bash
curl -X POST https://api.synthesisastrology.com/saved-charts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "chart_name": "John Doe",
    "birth_year": 1990,
    "birth_month": 6,
    "birth_day": 15,
    "birth_hour": 14,
    "birth_minute": 30,
    "birth_location": "New York, NY, USA",
    "chart_data_json": "{\"sidereal_major_positions\": [...]}"
  }'
```

### List Saved Charts

```bash
curl -X GET https://api.synthesisastrology.com/saved-charts \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get a Specific Chart

```bash
curl -X GET https://api.synthesisastrology.com/saved-charts/123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Delete a Chart

```bash
curl -X DELETE https://api.synthesisastrology.com/saved-charts/123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Famous People Matching

### Find Similar Famous People

```bash
curl -X POST https://api.synthesisastrology.com/api/find-similar-famous-people \
  -H "Content-Type: application/json" \
  -d '{
    "chart_data": {
      "sidereal_major_positions": [...],
      "tropical_major_positions": [...]
    },
    "limit": 10
  }'
```

**Response:**
```json
{
  "matches": [
    {
      "name": "Famous Person",
      "score": 85,
      "match_reasons": ["Sun sign", "Moon sign"],
      "planetary_placements": {...}
    }
  ],
  "total_compared": 5000,
  "matches_found": 10
}
```

---

## Synastry Analysis

### Compare Two Charts

```bash
curl -X POST https://api.synthesisastrology.com/synastry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "person1": {
      "full_name": "John Doe",
      "year": 1990,
      "month": 6,
      "day": 15,
      "hour": 14,
      "minute": 30,
      "location": "New York, NY, USA"
    },
    "person2": {
      "full_name": "Jane Smith",
      "year": 1985,
      "month": 3,
      "day": 20,
      "hour": 10,
      "minute": 0,
      "location": "Los Angeles, CA, USA"
    }
  }'
```

---

## Webhooks

### Create a Webhook

```bash
curl -X POST https://api.synthesisastrology.com/webhooks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "url": "https://your-app.com/webhook",
    "events": ["chart.calculated", "reading.generated"],
    "secret": "your-webhook-secret"
  }'
```

**Response:**
```json
{
  "id": "webhook-123",
  "url": "https://your-app.com/webhook",
  "events": ["chart.calculated", "reading.generated"],
  "active": true,
  "created_at": "2025-01-22T12:00:00"
}
```

### List Webhooks

```bash
curl -X GET https://api.synthesisastrology.com/webhooks \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test a Webhook

```bash
curl -X POST https://api.synthesisastrology.com/webhooks/webhook-123/test \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## API Keys

### Generate an API Key

```bash
curl -X POST https://api.synthesisastrology.com/api-keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "Production API Key",
    "expires_days": 365
  }'
```

**Response:**
```json
{
  "id": "key-123",
  "key": "sk_abc123...",
  "key_prefix": "sk_abc123",
  "name": "Production API Key",
  "created_at": "2025-01-22T12:00:00",
  "expires_at": "2026-01-22T12:00:00",
  "usage_count": 0,
  "is_active": true
}
```

**Important:** The full key is only shown once. Store it securely!

### List API Keys

```bash
curl -X GET https://api.synthesisastrology.com/api-keys \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Using API Key

```bash
curl -X POST https://api.synthesisastrology.com/calculate_chart \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_abc123..." \
  -d '{
    "full_name": "John Doe",
    "year": 1990,
    "month": 6,
    "day": 15,
    "hour": 14,
    "minute": 30,
    "location": "New York, NY, USA"
  }'
```

---

## Batch Processing

### Batch Chart Calculations

```bash
curl -X POST https://api.synthesisastrology.com/batch/charts \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "items": [
      {
        "full_name": "John Doe",
        "year": 1990,
        "month": 6,
        "day": 15,
        "hour": 14,
        "minute": 30,
        "location": "New York, NY, USA"
      },
      {
        "full_name": "Jane Smith",
        "year": 1985,
        "month": 3,
        "day": 20,
        "hour": 10,
        "minute": 0,
        "location": "Los Angeles, CA, USA"
      }
    ]
  }'
```

**Response:**
```json
{
  "id": "job-123",
  "type": "charts",
  "status": "pending",
  "total_items": 2,
  "processed_items": 0,
  "successful_items": 0,
  "failed_items": 0,
  "progress_percent": 0.0,
  "created_at": "2025-01-22T12:00:00"
}
```

### Check Batch Job Status

```bash
curl -X GET https://api.synthesisastrology.com/batch/job-123 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (when complete):**
```json
{
  "id": "job-123",
  "type": "charts",
  "status": "completed",
  "total_items": 2,
  "processed_items": 2,
  "successful_items": 2,
  "failed_items": 0,
  "progress_percent": 100.0,
  "created_at": "2025-01-22T12:00:00",
  "started_at": "2025-01-22T12:00:01",
  "completed_at": "2025-01-22T12:00:05",
  "results": [
    {
      "index": 0,
      "item": {...},
      "result": {...},
      "success": true
    }
  ]
}
```

---

## Analytics

### Get Usage Statistics (Admin Only)

```bash
curl -X GET "https://api.synthesisastrology.com/analytics/usage?days=30" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "total_events": 10000,
  "events_by_type": {
    "chart.calculated": 5000,
    "reading.generated": 2000,
    "api.request": 3000
  },
  "unique_users_count": 500,
  "events_by_day": {
    "2025-01-22": 500,
    "2025-01-21": 450
  }
}
```

### Get User Activity

```bash
curl -X GET "https://api.synthesisastrology.com/analytics/user/123?days=30" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Health Checks

### Ping

```bash
curl -X GET https://api.synthesisastrology.com/ping
```

**Response:**
```json
{
  "message": "ok"
}
```

### Health Check

```bash
curl -X GET https://api.synthesisastrology.com/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-22T12:00:00",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 5.2,
      "pool": {
        "size": 5,
        "checked_in": 3,
        "checked_out": 2
      }
    },
    "cache": {
      "status": "healthy",
      "type": "redis",
      "response_time_ms": 1.5
    },
    "ephemeris": {
      "status": "healthy",
      "path": "/app/swiss_ephemeris"
    }
  }
}
```

### Readiness Probe

```bash
curl -X GET https://api.synthesisastrology.com/health/ready
```

**Response:**
```json
{
  "ready": true,
  "status": "ready",
  "timestamp": "2025-01-22T12:00:00",
  "database": "healthy"
}
```

### Liveness Probe

```bash
curl -X GET https://api.synthesisastrology.com/health/live
```

**Response:**
```json
{
  "alive": true,
  "status": "alive",
  "timestamp": "2025-01-22T12:00:00"
}
```

---

## Error Handling

### Standard Error Response

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

### Common Error Codes

- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Not authorized
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service unavailable

### Example Error Response

```json
{
  "detail": "Could not find location data for 'Invalid Location'. Please be more specific (e.g., City, State, Country)."
}
```

---

## Rate Limiting

### Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 195
X-RateLimit-Reset: 1705939200
```

### Rate Limit Exceeded

When rate limit is exceeded:

**Status:** `429 Too Many Requests`

**Response:**
```json
{
  "detail": "Rate limit exceeded: 200 per 1 day"
}
```

---

## Webhook Events

### Webhook Payload Format

```json
{
  "event": "chart.calculated",
  "data": {
    "chart_id": "abc123",
    "user_id": 456,
    "chart_name": "John Doe"
  },
  "timestamp": "2025-01-22T12:00:00",
  "webhook_id": "webhook-123"
}
```

### Webhook Signature

Webhooks include an HMAC SHA256 signature in the `X-Webhook-Signature` header:

```
X-Webhook-Signature: sha256=abc123...
```

Verify the signature using your webhook secret:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        json.dumps(payload, sort_keys=True).encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## Best Practices

### 1. Error Handling

Always check for errors:

```python
import requests

response = requests.post(url, json=data)
if response.status_code >= 400:
    error = response.json()
    print(f"Error: {error['detail']}")
else:
    result = response.json()
    # Process result
```

### 2. Rate Limiting

Monitor rate limit headers:

```python
response = requests.post(url, json=data)
remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
if remaining < 10:
    print("Rate limit low, consider waiting")
```

### 3. Authentication

Store tokens securely:

```python
import os

token = os.getenv('SYNTHESIS_API_TOKEN')
headers = {'Authorization': f'Bearer {token}'}
```

### 4. Retry Logic

Implement retry for transient errors:

```python
import time
import requests

def request_with_retry(url, data, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code < 500:
                return response
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
    return response
```

### 5. Batch Processing

Use batch endpoints for multiple operations:

```python
# Instead of 100 individual requests
items = [chart1, chart2, ..., chart100]
response = requests.post(
    'https://api.synthesisastrology.com/batch/charts',
    json={'items': items},
    headers={'Authorization': f'Bearer {token}'}
)
job_id = response.json()['id']

# Poll for completion
while True:
    status = requests.get(
        f'https://api.synthesisastrology.com/batch/{job_id}',
        headers={'Authorization': f'Bearer {token}'}
    ).json()
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(2)
```

---

## SDK Examples

### Python

```python
import requests

class SynthesisAPI:
    def __init__(self, api_key=None, token=None):
        self.base_url = "https://api.synthesisastrology.com"
        self.headers = {}
        if token:
            self.headers['Authorization'] = f'Bearer {token}'
        elif api_key:
            self.headers['X-API-Key'] = api_key
    
    def calculate_chart(self, name, year, month, day, hour, minute, location):
        response = requests.post(
            f"{self.base_url}/calculate_chart",
            json={
                "full_name": name,
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "location": location
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
api = SynthesisAPI(token="your-token")
chart = api.calculate_chart("John Doe", 1990, 6, 15, 14, 30, "New York, NY, USA")
```

### JavaScript

```javascript
class SynthesisAPI {
  constructor(apiKey = null, token = null) {
    this.baseURL = 'https://api.synthesisastrology.com';
    this.headers = {
      'Content-Type': 'application/json'
    };
    if (token) {
      this.headers['Authorization'] = `Bearer ${token}`;
    } else if (apiKey) {
      this.headers['X-API-Key'] = apiKey;
    }
  }

  async calculateChart(name, year, month, day, hour, minute, location) {
    const response = await fetch(`${this.baseURL}/calculate_chart`, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify({
        full_name: name,
        year, month, day, hour, minute,
        location
      })
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  }
}

// Usage
const api = new SynthesisAPI(null, 'your-token');
const chart = await api.calculateChart('John Doe', 1990, 6, 15, 14, 30, 'New York, NY, USA');
```

---

**Last Updated:** 2025-01-22

