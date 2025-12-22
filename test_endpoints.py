"""
Quick endpoint verification script.

Tests that all endpoints are accessible and return expected status codes.
This is a basic smoke test - full integration tests should be added later.
"""

import requests
import json
import sys
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"  # Change if running on different port
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_endpoint(method: str, path: str, expected_status: int = 200, 
                  data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> bool:
    """Test a single endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            print(f"  ❌ Unsupported method: {method}")
            return False
        
        if response.status_code == expected_status:
            print(f"  ✅ {method} {path} - Status: {response.status_code}")
            return True
        else:
            print(f"  ⚠️  {method} {path} - Expected {expected_status}, got {response.status_code}")
            if response.status_code < 500:
                print(f"     Response: {response.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"  ❌ {method} {path} - Connection refused (is server running?)")
        return False
    except Exception as e:
        print(f"  ❌ {method} {path} - Error: {str(e)}")
        return False

def main():
    """Run endpoint tests."""
    print("=" * 60)
    print("Endpoint Verification Tests")
    print("=" * 60)
    print(f"Testing against: {BASE_URL}")
    print()
    
    results = []
    
    # Utility endpoints
    print("Testing Utility Endpoints:")
    results.append(("GET /", test_endpoint("GET", "/")))
    results.append(("GET /ping", test_endpoint("GET", "/ping")))
    results.append(("GET /check_email_config", test_endpoint("GET", "/check_email_config")))
    print()
    
    # Auth endpoints (will fail without valid data, but should return 422 not 404)
    print("Testing Auth Endpoints:")
    results.append(("POST /auth/register", test_endpoint("POST", "/auth/register", 
                                                          expected_status=422,  # Validation error expected
                                                          data={"email": "", "password": ""})))
    results.append(("POST /auth/login", test_endpoint("POST", "/auth/login", 
                                                      expected_status=422,  # Validation error expected
                                                      data={"email": "", "password": ""})))
    print()
    
    # Charts endpoints
    print("Testing Charts Endpoints:")
    results.append(("POST /calculate_chart", test_endpoint("POST", "/calculate_chart", 
                                                            expected_status=422,  # Validation error expected
                                                            data={})))
    results.append(("POST /generate_reading", test_endpoint("POST", "/generate_reading", 
                                                             expected_status=422,  # Validation error expected
                                                             data={})))
    print()
    
    # Saved charts endpoints (will fail without auth, but should return 401 not 404)
    print("Testing Saved Charts Endpoints:")
    results.append(("POST /charts/save", test_endpoint("POST", "/charts/save", 
                                                       expected_status=401,  # Auth required
                                                       data={})))
    results.append(("GET /charts/list", test_endpoint("GET", "/charts/list", 
                                                      expected_status=401)))  # Auth required
    print()
    
    # Subscription endpoints (will fail without auth, but should return 401 not 404)
    print("Testing Subscription Endpoints:")
    results.append(("GET /api/subscription/status", test_endpoint("GET", "/api/subscription/status", 
                                                                   expected_status=401)))  # Auth required
    print()
    
    # Utilities API endpoints
    print("Testing API Utility Endpoints:")
    results.append(("POST /api/log-clicks", test_endpoint("POST", "/api/log-clicks", 
                                                          expected_status=422,  # Validation error expected
                                                          data={})))
    print()
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All endpoints are accessible!")
        return 0
    else:
        print("⚠️  Some endpoints may have issues (expected for auth-required endpoints)")
        print("   Check that endpoints return proper error codes (401/422) not 404")
        return 1

if __name__ == "__main__":
    sys.exit(main())

