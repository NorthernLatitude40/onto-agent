#!/usr/bin/env python3
"""
Script to initialize vehicle tables in SQLite database for development
"""

import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

from src.common.database import engine

def init_vehicle_tables():
    """Create van_models and pricing_inventory tables if they don't exist"""
    print("🔧 Initializing vehicle tables...")

    from sqlalchemy import text

    with engine.connect() as conn:
        # Create van_models table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS van_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                berths INTEGER NOT NULL,
                transmission TEXT NOT NULL,
                specs TEXT,  -- JSON string for additional features
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

        # Create pricing_inventory table with foreign key to van_models
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pricing_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                pickup_date DATE NOT NULL,
                return_date DATE NOT NULL,
                price_nzd DECIMAL(10, 2) NOT NULL,
                is_available BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES van_models(id)
            )
        """))

        # Insert some sample data for testing
        conn.execute(text("""
            INSERT INTO van_models (model_name, berths, transmission, specs)
            VALUES ('Get Lost Campervan', 2, 'Automatic', '{\"solar\": true, \"battery\": \"100Ah\", \"heater\": \"Diesel\", \"bed\": \"Double\"}')
        """))

        conn.execute(text("""
            INSERT INTO pricing_inventory (model_id, pickup_date, return_date, price_nzd)
            VALUES (1, '2024-12-01', '2024-12-15', 99.99)
        """))

        conn.commit()
        print("✅ Vehicle tables created successfully with sample data!")

if __name__ == "__main__":
    init_vehicle_tables()