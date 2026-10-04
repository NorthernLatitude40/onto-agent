#!/usr/bin/env python3
"""Test the database query directly"""

from src.common.database import SessionLocal
from src.model.user_model import UserModel

# Test the query that was failing
db = SessionLocal()
try:
    print("Testing database query...")
    
    # This is what was failing before (checking email)
    print("\n1. Testing query with email filter (should fail)...")
    try:
        result = db.query(UserModel).filter(UserModel.email == "test@example.com").first()
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # This is what should work (checking openid only)
    print("\n2. Testing query with openid filter (should work)...")
    try:
        result = db.query(UserModel).filter(UserModel.openid == "testuser123").first()
        print(f"   Result: {result}")
        print("   ✓ Query successful!")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test creating a new user
    print("\n3. Testing user creation...")
    try:
        new_user = UserModel(openid="testuser123", email="test@example.com")
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        print(f"   ✓ User created with ID: {new_user.id}")
    except Exception as e:
        print(f"   ✗ Error creating user: {e}")

finally:
    db.close()
    print("\nDatabase connection closed")