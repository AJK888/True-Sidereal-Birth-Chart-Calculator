#!/usr/bin/env python3
"""Test script to verify Gemini API connection"""
import os
import google.generativeai as genai
import asyncio

async def test_gemini():
    """Test if Gemini API is working"""
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY environment variable is not set")
        print("   Set it in your Render dashboard or .env file")
        return False
    
    print(f"✓ GEMINI_API_KEY is set (length: {len(GEMINI_API_KEY)} characters)")
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("✓ Gemini API configured")
        
        model = genai.GenerativeModel('gemini-2.5-pro')
        print("✓ Gemini model initialized")
        
        print("  Testing with a simple prompt...")
        response = await model.generate_content_async("Say 'Hello, Gemini API is working!' in one sentence.")
        
        if response and response.text:
            print(f"✓ Gemini API responded: {response.text.strip()}")
            return True
        else:
            print("❌ Gemini API returned empty response")
            return False
            
    except Exception as e:
        print(f"❌ Error calling Gemini API: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Gemini API Connection")
    print("=" * 60)
    print()
    
    result = asyncio.run(test_gemini())
    
    print()
    print("=" * 60)
    if result:
        print("✓ Gemini API connection test PASSED")
    else:
        print("❌ Gemini API connection test FAILED")
    print("=" * 60)

