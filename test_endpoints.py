"""
Comprehensive endpoint verification script.

Tests that all migrated endpoints are accessible and return expected status codes.
This verifies that routers are properly integrated and endpoints are reachable.

Expected behavior:
- Public endpoints should return 200 or appropriate status
- Auth-required endpoints should return 401 (not 404) when unauthenticated
- Endpoints with invalid data should return 422 (validation error, not 404)
- 404 means the endpoint wasn't found (router not integrated properly)
"""

import requests
import json
import sys
from typing import Dict, Any, Tuple, List

# Configuration
BASE_URL = "http://localhost:8000"  # Change if running on different port
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_endpoint(method: str, path: str, expected_status: int = 200, 
                  data: Dict[str, Any] = None, headers: Dict[str, str] = None,
                  description: str = "") -> Tuple[bool, str]:
    """Test a single endpoint. Returns (success, message)."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            return False, f"Unsupported method: {method}"
        
        if response.status_code == expected_status:
            return True, f"[OK] {method} {path} - Status: {response.status_code}"
        elif response.status_code == 404:
            return False, f"[FAIL] {method} {path} - 404 NOT FOUND (router may not be integrated)"
        else:
            # Acceptable status codes (401 for auth, 422 for validation, etc.)
            if expected_status in [401, 422] and response.status_code in [401, 422]:
                return True, f"[OK] {method} {path} - Status: {response.status_code} (expected {expected_status})"
            else:
                error_msg = response.text[:150] if response.text else "No response body"
                return False, f"[WARN] {method} {path} - Expected {expected_status}, got {response.status_code}\n     {error_msg}"
    except requests.exceptions.ConnectionError:
        return False, f"[FAIL] {method} {path} - Connection refused (is server running on {BASE_URL}?)"
    except Exception as e:
        return False, f"[FAIL] {method} {path} - Error: {str(e)}"

def main():
    """Run comprehensive endpoint tests."""
    print("=" * 70)
    print("Endpoint Verification Tests - Router Migration")
    print("=" * 70)
    print(f"Testing against: {BASE_URL}")
    print("Note: 404 = endpoint not found (router issue), 401/422 = expected errors")
    print()
    
    results: List[Tuple[str, bool, str]] = []
    
    # Utility endpoints (no prefix)
    print("Testing Utility Endpoints (root):")
    success, msg = test_endpoint("GET", "/", expected_status=200)
    results.append(("GET /", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/ping", expected_status=200)
    results.append(("GET /ping", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/check_email_config", expected_status=200)
    results.append(("GET /check_email_config", success, msg))
    print(f"  {msg}")
    print()
    
    # Auth endpoints (prefix: /auth)
    print("Testing Auth Endpoints (/auth):")
    success, msg = test_endpoint("POST", "/auth/register", 
                                 expected_status=422,  # Validation error expected
                                 data={"email": "", "password": ""})
    results.append(("POST /auth/register", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/auth/login", 
                                 expected_status=422,  # Validation error expected
                                 data={"email": "", "password": ""})
    results.append(("POST /auth/login", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/auth/me", 
                                 expected_status=401)  # Auth required
    results.append(("GET /auth/me", success, msg))
    print(f"  {msg}")
    print()
    
    # Charts endpoints (no prefix)
    print("Testing Charts Endpoints:")
    success, msg = test_endpoint("POST", "/calculate_chart", 
                                 expected_status=422,  # Validation error expected
                                 data={})
    results.append(("POST /calculate_chart", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/generate_reading", 
                                 expected_status=422,  # Validation error expected
                                 data={})
    results.append(("POST /generate_reading", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/get_reading/test_hash", 
                                 expected_status=401)  # Auth required
    results.append(("GET /get_reading/{chart_hash}", success, msg))
    print(f"  {msg}")
    print()
    
    # Saved charts endpoints (prefix: /charts)
    print("Testing Saved Charts Endpoints (/charts):")
    success, msg = test_endpoint("POST", "/charts/save", 
                                 expected_status=401,  # Auth required
                                 data={})
    results.append(("POST /charts/save", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/charts/list", 
                                 expected_status=401)  # Auth required
    results.append(("GET /charts/list", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("GET", "/charts/1", 
                                 expected_status=401)  # Auth required
    results.append(("GET /charts/{chart_id}", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("DELETE", "/charts/1", 
                                 expected_status=401)  # Auth required
    results.append(("DELETE /charts/{chart_id}", success, msg))
    print(f"  {msg}")
    print()
    
    # Subscription endpoints (prefix: /api)
    print("Testing Subscription Endpoints (/api):")
    success, msg = test_endpoint("GET", "/api/subscription/status", 
                                 expected_status=401)  # Auth required
    results.append(("GET /api/subscription/status", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/api/reading/checkout", 
                                 expected_status=401)  # Auth required
    results.append(("POST /api/reading/checkout", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/api/subscription/checkout", 
                                 expected_status=401)  # Auth required
    results.append(("POST /api/subscription/checkout", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/api/webhooks/stripe", 
                                 expected_status=400)  # Missing signature expected
    results.append(("POST /api/webhooks/stripe", success, msg))
    print(f"  {msg}")
    
    success, msg = test_endpoint("POST", "/api/webhooks/render-deploy", 
                                 expected_status=200)  # May return 200 or error
    results.append(("POST /api/webhooks/render-deploy", success, msg))
    print(f"  {msg}")
    print()
    
    # Utilities API endpoints (prefix: /api)
    print("Testing API Utility Endpoints (/api):")
    success, msg = test_endpoint("POST", "/api/log-clicks", 
                                 expected_status=422,  # Validation error expected
                                 data={})
    results.append(("POST /api/log-clicks", success, msg))
    print(f"  {msg}")
    print()
    
    # Synastry endpoint (prefix: /api)
    print("Testing Synastry Endpoint (/api):")
    success, msg = test_endpoint("POST", "/api/synastry", 
                                 expected_status=422,  # Validation error expected
                                 data={})
    results.append(("POST /api/synastry", success, msg))
    print(f"  {msg}")
    print()
    
    # Summary
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    failed = total - passed
    
    print(f"Total endpoints tested: {total}")
    print(f"[PASS] Passed: {passed}")
    print(f"[FAIL] Failed: {failed}")
    print()
    
    if failed > 0:
        print("Failed endpoints:")
        for name, success, msg in results:
            if not success:
                print(f"  - {name}")
        print()
    
    # Check for 404 errors (router integration issues)
    has_404 = any("404" in msg for _, _, msg in results if not _)
    if has_404:
        print("[WARN] WARNING: Some endpoints returned 404!")
        print("   This indicates routers may not be properly integrated in api.py")
        print("   Check that all routers are included with app.include_router()")
        print()
    
    if passed == total:
        print("[SUCCESS] All endpoints are accessible and routers are properly integrated!")
        return 0
    elif not has_404:
        print("[SUCCESS] All endpoints found! Some may have expected validation/auth errors.")
        print("   This is normal - endpoints are working, just need valid data/auth.")
        return 0
    else:
        print("[ERROR] Some endpoints are not accessible (404 errors detected)")
        print("   Please check router integration in api.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())

