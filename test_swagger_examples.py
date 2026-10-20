#!/usr/bin/env python3
"""
Test script to verify Swagger examples are properly formatted
"""
import sys
sys.path.insert(0, ".")

from src.api.v1.endpoints.scraper_api import (
    ScrapeConfig,
    VehicleSpecs,
    ScrapedVehicle,
    ScrapeResponse
)

def test_models():
    """Test that all models can be instantiated with example data"""
    print("Testing model instantiation...")
    
    # Test VehicleSpecs
    try:
        specs = VehicleSpecs(
            solar=True,
            battery="100Ah LiFePO4",
            heater="Diesel",
            bed="Double bed"
        )
        print(f"✓ VehicleSpecs created: {specs}")
    except Exception as e:
        print(f"✗ VehicleSpecs failed: {e}")
        return False
    
    # Test ScrapedVehicle
    try:
        vehicle = ScrapedVehicle(
            model_name="4WD Campervan",
            berths=3,
            transmission="Manual",
            specs=specs,
            price_nzd=125.0,
            pickup_date="2026-11-10",
            return_date="2026-11-15"
        )
        print(f"✓ ScrapedVehicle created: {vehicle.model_name}")
    except Exception as e:
        print(f"✗ ScrapedVehicle failed: {e}")
        return False
    
    # Test ScrapeResponse
    try:
        response = ScrapeResponse(
            success=True,
            count=2,
            message="Scraping completed successfully",
            vehicles=[vehicle]
        )
        print(f"✓ ScrapeResponse created: {response.message}")
    except Exception as e:
        print(f"✗ ScrapeResponse failed: {e}")
        return False
    
    print("\n✓ All models instantiated successfully!")
    return True

if __name__ == "__main__":
    success = test_models()
    sys.exit(0 if success else 1)
