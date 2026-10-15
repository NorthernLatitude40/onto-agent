#!/usr/bin/env python3
"""
Simple test script for the scraper API endpoint - tests only POST
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

print("🧪 Testing Scraper API POST Endpoint...")
print("=" * 60)

# Test: POST /api/v1/scraper/scrape/vehicles (scrape and store)
print("\nTesting POST /api/v1/scraper/scrape/vehicles")
config = {
    "target_url": "https://getlostinnz.co.nz/",
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    },
    "timeout": 10
}
response = client.post("/api/v1/scraper/scrape/vehicles", json=config)
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Success: {data['success']}")
    print(f"Count: {data['count']}")
    print(f"Message: {data['message']}")
    if 'vehicles' in data and len(data['vehicles']) > 0:
        print(f"\nFirst vehicle:")
        print(f"  Model: {data['vehicles'][0]['model_name']}")
        print(f"  Price: ${data['vehicles'][0]['price_nzd']}")
        print(f"  Berths: {data['vehicles'][0]['berths']}")
else:
    print(f"Error: {response.text}")

print("\n" + "=" * 60)
print("✅ Test completed!")