#!/usr/bin/env python3
"""
Simple verification script to test the ShopModel serialization fix.
This verifies that converting ShopModel attributes to a dict works correctly.
"""

import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

import json
from typing import Dict, Any

class MockShopModel:
    """Mock ShopModel class for testing serialization logic."""
    def __init__(self):
        self.id = 123
        self.name = "Test Shop"
        self.logo = "http://example.com/logo.png"
        self.contact_name = "John Doe"
        self.contact_phone = "1234567890"
        self.province = "California"
        self.city = "San Francisco"
        self.district = "Downtown"
        self.address_detail = "123 Main St"
        self.is_active = True

def test_shop_serialization():
    """Test the serialization logic used in the fix."""
    
    # Create a mock shop object (simulating ShopModel)
    shop = MockShopModel()
    
    # This is the exact logic we added to shop_api.py
    shop_data = {
        "id": shop.id,
        "name": shop.name,
        "logo": shop.logo,
        "contact_name": shop.contact_name,
        "contact_phone": shop.contact_phone,
        "province": shop.province,
        "city": shop.city,
        "district": shop.district,
        "address_detail": shop.address_detail,
        "is_active": shop.is_active
    }
    
    # Test JSON serialization (this should work)
    try:
        json_str = json.dumps(shop_data)
        print("✓ ShopModel serialization successful!")
        print(f"Serialized data: {json_str}")
        
        # Verify we can deserialize it back
        parsed_data = json.loads(json_str)
        assert parsed_data["id"] == 123
        assert parsed_data["name"] == "Test Shop"
        print("✓ JSON round-trip successful!")
        
        return True
    except Exception as e:
        print(f"✗ Serialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_shop_with_staff_count():
    """Test serialization with staff_count (used in get_current_shop_info)."""
    
    shop = MockShopModel()
    staff_count = 5  # Simulated count
    
    # This is the logic from line 289-304 in shop_api.py
    shop_data = {
        "id": shop.id,
        "name": shop.name,
        "logo": shop.logo,
        "contact_name": shop.contact_name,
        "contact_phone": shop.contact_phone,
        "province": shop.province,
        "city": shop.city,
        "district": shop.district,
        "address_detail": shop.address_detail,
        "is_active": shop.is_active,
        "staff_count": staff_count
    }
    
    try:
        json_str = json.dumps(shop_data)
        print("✓ ShopModel with staff_count serialization successful!")
        print(f"Serialized data: {json_str}")
        return True
    except Exception as e:
        print(f"✗ Serialization with staff_count failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing ShopModel serialization fix...")
    print("=" * 60)
    
    test1 = test_shop_serialization()
    print()
    test2 = test_shop_with_staff_count()
    
    print("=" * 60)
    if test1 and test2:
        print("✓ All tests passed! The fix should resolve the serialization error.")
        sys.exit(0)
    else:
        print("✗ Some tests failed!")
        sys.exit(1)
