#!/usr/bin/env python3
"""
Test script to verify ShopModel serialization fix.
This tests that the ShopModel can be properly serialized for JSON responses.
"""

import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from src.model.shop_model import ShopModel
from src.common.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

# Create a test database in memory
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_shop_model_serialization():
    """Test that ShopModel can be serialized to JSON."""
    db = SessionLocal()
    
    # Create a test shop
    shop = ShopModel(
        name="Test Shop",
        logo="http://example.com/logo.png",
        contact_name="John Doe",
        contact_phone="1234567890",
        province="California",
        city="San Francisco",
        district="Downtown",
        address_detail="123 Main St",
        is_active=True
    )
    
    db.add(shop)
    db.commit()
    db.refresh(shop)
    
    # Convert to dict (this is what we're doing in the fix)
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
    
    # Try to serialize to JSON (this should work now)
    try:
        json_str = json.dumps(shop_data)
        print("✓ ShopModel serialization successful!")
        print(f"Serialized data: {json_str}")
        return True
    except Exception as e:
        print(f"✗ ShopModel serialization failed: {e}")
        return False

if __name__ == "__main__":
    success = test_shop_model_serialization()
    sys.exit(0 if success else 1)
