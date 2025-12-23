"""
Load Testing Script

Script for load testing the API endpoints.
"""

import requests
import time
import concurrent.futures
from typing import List, Dict, Any
import statistics


def test_endpoint(url: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
    """Test a single endpoint."""
    start = time.time()
    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        duration = time.time() - start
        
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "duration": duration,
            "error": None
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "success": False,
            "status_code": None,
            "duration": duration,
            "error": str(e)
        }


def load_test(
    url: str,
    num_requests: int = 100,
    concurrent_requests: int = 10,
    method: str = "GET",
    **kwargs
) -> Dict[str, Any]:
    """Run a load test on an endpoint."""
    print(f"Starting load test: {num_requests} requests, {concurrent_requests} concurrent")
    
    results = []
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [
            executor.submit(test_endpoint, url, method, **kwargs)
            for _ in range(num_requests)
        ]
        
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    durations = [r["duration"] for r in results]
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]
    
    return {
        "total_requests": num_requests,
        "successful": len(successes),
        "failed": len(failures),
        "success_rate": len(successes) / num_requests * 100,
        "total_time": total_time,
        "requests_per_second": num_requests / total_time,
        "durations": {
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "avg": statistics.mean(durations) if durations else 0,
            "median": statistics.median(durations) if durations else 0,
            "p95": sorted(durations)[int(len(durations) * 0.95)] if durations else 0,
            "p99": sorted(durations)[int(len(durations) * 0.99)] if durations else 0,
        },
        "errors": [r["error"] for r in failures if r["error"]]
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python load_test.py <url> [num_requests] [concurrent]")
        sys.exit(1)
    
    url = sys.argv[1]
    num_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    concurrent = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    results = load_test(url, num_requests, concurrent)
    
    print("\n" + "="*50)
    print("Load Test Results")
    print("="*50)
    print(f"Total Requests: {results['total_requests']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {results['success_rate']:.2f}%")
    print(f"Total Time: {results['total_time']:.2f}s")
    print(f"Requests/Second: {results['requests_per_second']:.2f}")
    print("\nResponse Times:")
    print(f"  Min: {results['durations']['min']:.3f}s")
    print(f"  Max: {results['durations']['max']:.3f}s")
    print(f"  Avg: {results['durations']['avg']:.3f}s")
    print(f"  Median: {results['durations']['median']:.3f}s")
    print(f"  P95: {results['durations']['p95']:.3f}s")
    print(f"  P99: {results['durations']['p99']:.3f}s")
    
    if results['errors']:
        print(f"\nErrors: {len(results['errors'])}")
        for error in set(results['errors'][:10]):
            print(f"  - {error}")

