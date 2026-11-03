#!/usr/bin/env python3
"""
Script to examine database schema using information_schema
"""

import sys
import os
from sqlalchemy import create_engine, text

# Use SQLite for local development (same as the app)
DATABASE_URL = "sqlite:///./agent_api.db"

def get_database_schema():
    """Get table structure from information_schema"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as connection:
        result = connection.execute(text("""
            SELECT name AS table_name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """))

        tables = {}
        for row in result:
            table_name = row[0]
            if not table_name.startswith('sqlite_'):
                # Get columns for this table
                col_result = connection.execute(text(f"""
                    PRAGMA table_info({table_name})
                """))
                columns = []
                for col_row in col_result:
                    cid, name, type_, notnull, dflt_value, pk = col_row
                    columns.append({
                        'name': name,
                        'type': type_,
                        'nullable': notnull == 0,
                        'default': dflt_value,
                        'primary_key': pk == 1
                    })
                tables[table_name] = columns

        return tables

def print_schema(tables):
    """Print schema in readable format"""
    print("Database Schema:")
    print("=" * 80)

    for table_name, columns in sorted(tables.items()):
        print(f"\nTable: {table_name}")
        print("-" * 40)
        for col in columns:
            type_str = f"{col['type']}"
            nullable = " (nullable)" if col['nullable'] else ""
            pk = " (PK)" if col['primary_key'] else ""
            default = f" [default: {col['default']}]" if col['default'] else ""
            print(f"  {col['name']}: {type_str}{nullable}{pk}{default}")

if __name__ == "__main__":
    try:
        schema = get_database_schema()
        print_schema(schema)

        # Return JSON for programmatic use
        import json
        print("\n" + "=" * 80)
        print("JSON Output:")
        print(json.dumps(schema, indent=2))

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)