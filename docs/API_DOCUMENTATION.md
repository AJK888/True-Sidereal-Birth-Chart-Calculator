# API Documentation

## Overview

The Synthesis Astrology API provides endpoints for calculating birth charts, generating astrological readings, and finding similar famous people.

**Base URL**: `https://true-sidereal-api.onrender.com`

**API Version**: v1

**Interactive Documentation**: 
- Swagger UI: `/docs`
- ReDoc: `/redoc`

---

## Authentication

Most endpoints support optional authentication. Some features require authentication:
- Saving charts
- Accessing saved charts
- Subscription features

### Authentication Methods

1. **Bearer Token** (Recommended)
   ```
   Authorization: Bearer <access_token>
   ```

2. **Cookie** (Alternative)
   ```
   Cookie: access_token=<access_token>
   ```

### Getting an Access Token

**Register a new user:**
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

**Login:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

Response includes `access_token`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "John Doe"
  }
}
```

---

## Rate Limiting

- **Chart Calculations**: 200 requests per day per IP address
- **Other Endpoints**: Varies by endpoint
- **Rate Limit Headers**: 
  - `X-RateLimit-Limit`: Maximum requests allowed
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Time when limit resets

---

## Endpoints

### Charts

#### Calculate Chart

Calculate a complete birth chart with all astrological data.

```http
POST /api/v1/calculate_chart
Content-Type: application/json
Authorization: Bearer <token> (optional)

{
  "full_name": "John Doe",
  "year": 1990,
  "month": 6,
  "day": 15,
  "hour": 14,
  "minute": 30,
  "location": "New York, NY, USA",
  "unknown_time": false,
  "user_email": "user@example.com",
  "is_full_birth_name": true
}
```

**Response:**
```json
{
  "sidereal_major_positions": [...],
  "tropical_major_positions": [...],
  "sidereal_aspects": [...],
  "tropical_aspects": [...],
  "sidereal_house_cusps": [...],
  "tropical_house_cusps": [...],
  "numerology": {
    "life_path_number": 5,
    "day_number": 1,
    "lucky_number": 7
  },
  "chinese_zodiac": "Horse",
  "snapshot_reading": "...",
  "quick_highlights": "...",
  "chart_hash": "abc123..."
}
```

**Transit Charts:**

To calculate current planetary positions, set `full_name` to "Current Transits":

```json
{
  "full_name": "Current Transits",
  "year": 2025,
  "month": 1,
  "day": 22,
  "hour": 14,
  "minute": 30,
  "location": "New York, NY, USA",
  "unknown_time": false
}
```

#### Get Reading

Retrieve a generated reading by chart hash.

```http
GET /api/v1/get_reading/{chart_hash}
Authorization: Bearer <token>
```

---

### Famous People

#### Find Similar Famous People

Find famous people with similar astrological charts.

```http
POST /api/find-similar-famous-people
Content-Type: application/json

{
  "chart_data": {
    "sidereal_major_positions": [...],
    "tropical_major_positions": [...],
    ...
  },
  "limit": 10
}
```

**Response:**
```json
{
  "matches": [
    {
      "name": "Famous Person",
      "wikipedia_url": "https://...",
      "occupation": "Actor",
      "similarity_score": 85.5,
      "matching_factors": [...],
      "birth_date": "6/15/1990",
      "birth_location": "New York, NY, USA"
    }
  ],
  "total_compared": 3451,
  "message": "Found 10 similar famous people"
}
```

**Note**: Results are cached for 24 hours. Subsequent requests with the same chart data will return cached results.

---

### Authentication

#### Register

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

#### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

#### Get Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

---

### Saved Charts

#### List Saved Charts

```http
GET /api/v1/saved-charts
Authorization: Bearer <token>
```

#### Get Saved Chart

```http
GET /api/v1/saved-charts/{chart_id}
Authorization: Bearer <token>
```

#### Save Chart

```http
POST /api/v1/saved-charts
Authorization: Bearer <token>
Content-Type: application/json

{
  "chart_name": "My Birth Chart",
  "birth_year": 1990,
  "birth_month": 6,
  "birth_day": 15,
  "birth_location": "New York, NY, USA",
  "chart_data_json": "{...}",
  "unknown_time": false
}
```

#### Delete Saved Chart

```http
DELETE /api/v1/saved-charts/{chart_id}
Authorization: Bearer <token>
```

---

### Synastry

#### Generate Synastry Analysis

Compare two birth charts for relationship compatibility.

```http
POST /api/v1/synastry
Content-Type: application/json

{
  "person1_data": "Full reading text and placements...",
  "person2_data": "Full reading text and placements...",
  "user_email": "user@example.com"
}
```

**Note**: Analysis is generated asynchronously and sent via email.

---

### Utilities

#### Health Check

```http
GET /ping
```

#### Metrics

```http
GET /api/v1/metrics
```

Returns performance metrics and health status.

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error
- `503 Service Unavailable`: Service temporarily unavailable

---

## Data Models

### ChartRequest

```json
{
  "full_name": "string (required, 1-255 chars)",
  "year": "integer (required, 1900-2100)",
  "month": "integer (required, 1-12)",
  "day": "integer (required, 1-31)",
  "hour": "integer (required, 0-23)",
  "minute": "integer (required, 0-59)",
  "location": "string (required, 2-500 chars)",
  "unknown_time": "boolean (default: false)",
  "user_email": "string (optional, email format)",
  "is_full_birth_name": "boolean (default: false)"
}
```

### Chart Response

The chart response includes:

- **sidereal_major_positions**: Planetary positions in sidereal zodiac
- **tropical_major_positions**: Planetary positions in tropical zodiac
- **sidereal_aspects**: Planetary aspects (sidereal)
- **tropical_aspects**: Planetary aspects (tropical)
- **sidereal_house_cusps**: House cusps (sidereal)
- **tropical_house_cusps**: House cusps (tropical)
- **numerology**: Life path, day number, lucky number
- **chinese_zodiac**: Animal and element
- **snapshot_reading**: AI-generated brief reading
- **quick_highlights**: Key chart highlights
- **chart_hash**: Unique identifier for the chart

---

## Examples

### Python

```python
import requests

# Calculate chart
response = requests.post(
    "https://true-sidereal-api.onrender.com/api/v1/calculate_chart",
    json={
        "full_name": "John Doe",
        "year": 1990,
        "month": 6,
        "day": 15,
        "hour": 14,
        "minute": 30,
        "location": "New York, NY, USA",
        "unknown_time": False
    }
)

chart_data = response.json()
print(f"Chart hash: {chart_data['chart_hash']}")

# Find similar famous people
famous_response = requests.post(
    "https://true-sidereal-api.onrender.com/api/find-similar-famous-people",
    json={
        "chart_data": chart_data,
        "limit": 10
    }
)

matches = famous_response.json()
print(f"Found {len(matches['matches'])} similar people")
```

### JavaScript

```javascript
// Calculate chart
const response = await fetch('https://true-sidereal-api.onrender.com/api/v1/calculate_chart', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    full_name: 'John Doe',
    year: 1990,
    month: 6,
    day: 15,
    hour: 14,
    minute: 30,
    location: 'New York, NY, USA',
    unknown_time: false
  })
});

const chartData = await response.json();
console.log('Chart hash:', chartData.chart_hash);
```

---

## Support

For API support, contact: support@synthesisastrology.com

---

**Last Updated**: 2025-01-22

