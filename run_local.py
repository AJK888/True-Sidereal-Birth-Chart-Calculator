#!/usr/bin/env python3
"""
Local development server runner for the True Sidereal API.
This script starts the FastAPI server with hot-reload for local debugging.
"""
import uvicorn
import os
import sys

if __name__ == "__main__":
    # Check if required environment variables are set
    required_vars = {
        "OPENCAGE_KEY": "OpenCage Geocoding API key",
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("⚠️  Warning: Some recommended environment variables are not set:")
        for var in missing_vars:
            print(var)
        print("\nThe server will start, but some features may not work.")
        print("Optional variables: GEMINI_API_KEY, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, ADMIN_EMAIL, ADMIN_SECRET_KEY")
        print()
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "127.0.0.1")
    
    print("="*60)
    print("Starting True Sidereal API - Local Development Server")
    print("="*60)
    print(f"Server will be available at: http://{host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Alternative docs: http://{host}:{port}/redoc")
    print("="*60)
    print("Press Ctrl+C to stop the server")
    print("="*60)
    print()
    
    # Start the server with hot-reload
    uvicorn.run(
        "api:app",
        host=host,
        port=port,
        reload=True,  # Enable hot-reload for development
        log_level="info"
    )

