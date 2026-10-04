#!/usr/bin/env python3
"""Test script to verify the registration API fix"""

import requests
import json

# Test data
test_user = {
    "username": "testuser123",
    "email": "test@example.com",
    "password": "password123"
}

# API endpoint
url = "http://localhost:8000/api/v1/register"

print("Testing registration API fix...")
print(f"Sending request to {url}")
print(f"Test data: {json.dumps(test_user, indent=2)}")

try:
    response = requests.post(url, json=test_user)
    print(f"\nResponse status code: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        print("\n✓ Registration successful!")
        print(f"User ID: {data.get('data', {}).get('user_id')}")
        print(f"Username: {data.get('data', {}).get('username')}")
    else:
        print("\n✗ Registration failed!")
        
except Exception as e:
    print(f"\nError occurred: {e}")