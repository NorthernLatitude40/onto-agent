#!/usr/bin/env python3
"""
Test script for user registration API
"""

import requests
import json

def test_register_user():
    """Test the registration endpoint"""
    
    url = "http://localhost:8000/api/v1/auth/register"
    
    # Test data
    test_users = [
        {
            "username": "testuser1",
            "email": "test1@example.com",
            "password": "password123"
        },
        {
            "username": "testuser2", 
            "email": "test2@example.com",
            "password": "mypassword456"
        }
    ]
    
    for user in test_users:
        print(f"\nTesting registration for: {user['username']}")
        try:
            response = requests.post(url, json=user)
            data = response.json()
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(data, indent=2)}")
            
            if response.ok and data.get('success'):
                print("✓ Registration successful!")
            else:
                print(f"✗ Registration failed: {data.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_register_user()