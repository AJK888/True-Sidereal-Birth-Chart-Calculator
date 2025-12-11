# Wikipedia API Compliance Guide

## Current Implementation Status

### ✅ What's Good:
1. **Uses `wikipedia-api` library** - This is a legitimate Python wrapper for Wikipedia's API
2. **Has rate limiting** - `REQUEST_DELAY = 1.0` seconds between requests
3. **Respectful approach** - Doesn't hammer the servers

### ⚠️ What Needs Improvement:

#### 1. **Rate Limiting Compliance**
Wikipedia doesn't publish exact numbers, but safe practices are:
- **100-200 requests/minute** = generally OK (no token needed)
- This equals 6,000-12,000 requests/hour

**Current Implementation**: 
- Fixed version uses 100 requests/minute = 0.6 seconds between requests
- This is well within the safe range
- For 2000 people: ~20 minutes total (much faster!)

#### 2. **Missing User-Agent**
Wikipedia **requires** a User-Agent header that identifies your application:
```
User-Agent: YourAppName/1.0 (contact@youremail.com)
```

#### 3. **No Error Handling for Rate Limits**
Wikipedia returns HTTP 429 (Too Many Requests) when you exceed limits. The script doesn't handle this.

#### 4. **No Retry Logic**
Should implement exponential backoff for failed requests.

## How the Current Script Works

1. **Uses `wikipedia-api` library** - This library makes requests to Wikipedia's REST API
2. **Fetches page content** - Gets the full text of Wikipedia pages
3. **Parses infobox data** - Uses regex to extract birth dates and locations
4. **Rate limiting** - Waits 1 second between requests (but this is too fast!)

## Wikipedia's Terms of Service

From Wikipedia's Terms of Use:
- ✅ **Allowed**: Automated access via API for reasonable use
- ✅ **Allowed**: Caching data for your own use
- ⚠️ **Required**: Identify your bot/application with User-Agent
- ⚠️ **Required**: Respect rate limits
- ❌ **Not allowed**: Scraping HTML directly (should use API)
- ❌ **Not allowed**: Overwhelming servers with requests

## Recommended Implementation

### Safe Rate Limiting (No Token Needed)
```python
REQUEST_DELAY = 0.6  # 100 requests/minute (safe, conservative)
# OR
REQUEST_DELAY = 0.3  # 200 requests/minute (still safe, faster)
```

**Benefits:**
- No authentication needed
- Fast enough: 2000 people in ~10-20 minutes
- Well within safe limits
- Simple to implement

### For Even Faster Access (Optional)
- Get Wikipedia API token for authenticated requests
- May allow slightly higher rates
- But not necessary for this use case

## Fixed Implementation

See `scrape_wikipedia_famous_people_fixed.py` for a compliant version.

