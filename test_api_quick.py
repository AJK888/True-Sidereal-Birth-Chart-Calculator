#!/usr/bin/env python3
"""Quick test to see if API is responding"""
import os
import requests

API_BASE = "https://true-sidereal-api.onrender.com"
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY")
if not ADMIN_SECRET:
    print("Warning: ADMIN_SECRET_KEY environment variable not set. Rate limiting may apply.")

print("Testing API connection...")
print(f"URL: {API_BASE}/ping")

try:
    response = requests.get(f"{API_BASE}/ping", timeout=10)
    print(f"✓ Ping successful: {response.status_code}")
    print(f"  Response: {response.json()}")
except Exception as e:
    print(f"✗ Ping failed: {e}")

print("\nTesting calculate_chart with minimal data...")
test_payload = {
    "full_name": "Test User",
    "year": 2000,
    "month": 1,
    "day": 1,
    "hour": 12,
    "minute": 0,
    "location": "New York, NY, USA",
    "unknown_time": False,
    "no_full_name": False
}

try:
    headers = {"x-admin-secret": ADMIN_SECRET}
    print("Sending request (30 second timeout)...")
    response = requests.post(
        f"{API_BASE}/calculate_chart",
        json=test_payload,
        headers=headers,
        timeout=(10, 30)  # Short timeout for testing
    )
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        print("✓ Chart calculation works!")
    else:
        print(f"✗ Error: {response.text[:200]}")
except requests.exceptions.Timeout:
    print("✗ Request timed out (API may be slow or sleeping)")
except Exception as e:
    print(f"✗ Error: {e}")

