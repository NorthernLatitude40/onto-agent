#!/usr/bin/env python3
"""
Test script for the scraper API endpoint
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from fastapi.testclient import TestClient
from src.api.v1.router import api_v1_router
from fastapi import FastAPI

# Create a test app
app = FastAPI()
app.include_router(api_v1_router)

client = TestClient(app)

print("🧪 Testing Scraper API Endpoints...")
print("=" * 60)

# Test 1: GET /api/v1/scraper/scrape-vehicles (get stored vehicles)
print("\n1. Testing GET /api/v1/scraper/scrape-vehicles")
response = client.get("/api/v1/scraper/scrape-vehicles")
print(f"   Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Response: {data}")
else:
    print(f"   Error: {response.text}")

# Test 2: POST /api/v1/scraper/scrape-vehicles (scrape and store)
print("\n2. Testing POST /api/v1/scraper/scrape-vehicles")
config = {
    "target_url": "https://getlostinnz.co.nz/",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "timeout": 10
}
response = client.post("/api/v1/scraper/scrape-vehicles", json=config)
print(f"   Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Success: {data['success']}")
    if 'count' in data.get('data', {}):
        print(f"   Count: {data['data']['count']}")
    if 'message' in data.get('data', {}):
        print(f"   Message: {data['data']['message']}")
else:
    print(f"   Error: {response.text}")

# Test 3: GET again to verify data was stored
print("\n3. Testing GET /api/v1/scraper/scrape-vehicles (after POST)")
response = client.get("/api/v1/scraper/scrape-vehicles")
print(f"   Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"   Number of vehicles retrieved: {len(data)}")
else:
    print(f"   Error: {response.text}")

print("\n" + "=" * 60)
print("✅ All tests completed!")