#!/usr/bin/env python3
"""
Test script to verify vehicle data in PostgreSQL database
"""
import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from src.common.database import SessionLocal

print("🔍 Checking database tables and vehicle data...")
print("=" * 60)

# Connect to database
db = SessionLocal()
try:
    # Check if van_models table exists
    from sqlalchemy import text
    result = db.execute(text("SELECT to_regclass('van_models')")).fetchone()
    if result and result[0]:
        print("✓ van_models table exists")
    
    # Check if pricing_inventory table exists
    result = db.execute(text("SELECT to_regclass('pricing_inventory')")).fetchone()
    if result and result[0]:
        print("✓ pricing_inventory table exists")
    
    # Count records in van_models
    result = db.execute(text("SELECT COUNT(*) FROM van_models")).fetchone()
    count = result[0] if result else 0
    print(f"\n📊 Vehicle Models in Database: {count}")
    
    # Show sample records
    if count > 0:
        print("\n📋 Sample Vehicle Records:")
        rows = db.execute(text("SELECT * FROM van_models LIMIT 3")).fetchall()
        for i, row in enumerate(rows, 1):
            print(f"\n{i}. Model: {row[1]}")
            print(f"   Berths: {row.berths}, Transmission: {row.transmission}")
    
    # Count records in pricing_inventory
    result = db.execute(text("SELECT COUNT(*) FROM pricing_inventory")).fetchone()
    count = result[0] if result else 0
    print(f"\n💰 Pricing Inventory Records: {count}")
    
    # Show sample pricing records
    if count > 0:
        print("\n📋 Sample Pricing Records:")
        rows = db.execute(text("SELECT * FROM pricing_inventory LIMIT 3")).fetchall()
        for i, row in enumerate(rows, 1):
            print(f"\n{i}. Model ID: {row[0]}, Price NZD: ${row[2]:.2f}")
            print(f"   Pickup: {row[3]}, Return: {row[4]}")

finally:
    db.close()

print("\n" + "=" * 60)
print("✅ Database verification complete!")
