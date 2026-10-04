#!/usr/bin/env python3
"""
Test script to verify the registration API fix
"""
import httpx
import asyncio

async def test_registration():
    base_url = "http://localhost:8000"
    
    # Test 1: Valid registration
    print("Testing valid registration...")
    data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Try both endpoints
            for endpoint in ["api/v1/register", "api/v1/auth/register"]:
                url = f"{base_url}/{endpoint}"
                print(f"\nTrying endpoint: {url}")
                response = await client.post(url, json=data)
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")
                
                if response.status_code == 200:
                    print("✓ Registration successful!")
                    return True
                elif response.status_code == 422:
                    print("✗ Still getting 422 error - validation issue")
                else:
                    print(f"✗ Unexpected status code: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return False

if __name__ == "__main__":
    success = asyncio.run(test_registration())
    if not success:
        print("\n⚠️  Registration API test failed")
        exit(1)
