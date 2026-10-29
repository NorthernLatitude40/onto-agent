#!/usr/bin/env python3
"""
Dynamic Database Introspection API for PostgreSQL/SQLite

This module provides endpoints to dynamically fetch database table structures,
column information, and data types from the connected database.
"""

import sys
sys.path.insert(0, '/workspace/langgraph_workspace')

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from sqlalchemy import inspect, text
from src.common.database import engine

router = APIRouter(prefix="/api/v1/database", tags=["database-introspection"])

@router.get("/tables", response_model=List[Dict[str, Any]])
async def get_database_tables():
    """
    Get all tables in the database with their structure information.

    Returns:
        List of dictionaries containing table name and column information
    """
    try:
        inspector = inspect(engine)
        tables = []

        # Get all table names
        table_names = inspector.get_table_names()

        for table_name in table_names:
            if table_name.startswith('sqlite_'):  # Skip system tables
                continue

            columns = []
            column_info = inspector.get_columns(table_name)

            for col in column_info:
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "default": col.get("default"),
                    "autoincrement": col.get("autoincrement", False)
                })

            tables.append({
                "table_name": table_name,
                "columns": columns
            })

        return sorted(tables, key=lambda x: x["table_name"])

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database introspection failed: {str(e)}"
        )

@router.get("/tables/{table_name}", response_model=Dict[str, Any])
async def get_table_structure(table_name: str):
    """
    Get detailed structure information for a specific table.

    Args:
        table_name: Name of the table to inspect

    Returns:
        Dictionary containing table structure and sample data
    """
    try:
        inspector = inspect(engine)

        # Check if table exists
        if table_name not in inspector.get_table_names():
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )

        # Get column information
        columns = []
        column_info = inspector.get_columns(table_name)

        for col in column_info:
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": col.get("default"),
                "autoincrement": col.get("autoincrement", False)
            })

        # Get primary key information
        primary_keys = []
        try:
            pk_info = inspector.get_pk_constraint(table_name)
            if pk_info and "constrained_columns" in pk_info:
                primary_keys = [col["name"] for col in pk_info["constrained_columns"]]
        except Exception as e:
            # Handle cases where primary key info is not available
            pass

        # Get foreign key information
        fk_info = inspector.get_foreign_keys(table_name)
        foreign_keys = []
        for fk in fk_info:
            foreign_keys.append({
                "column": fk["constrained_columns"][0],
                "referenced_table": fk["referred_table"],
                "referenced_column": fk["referred_columns"][0]
            })

        # Get sample data (limit to 5 rows)
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT 5"))
            rows = result.fetchall()
            sample_data = []
            for row in rows:
                sample_data.append(dict(row._mapping))

        return {
            "table_name": table_name,
            "columns": columns,
            "primary_keys": primary_keys,
            "foreign_keys": foreign_keys,
            "sample_data": sample_data
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table structure: {str(e)}"
        )

@router.get("/tables/{table_name}/columns", response_model=List[Dict[str, Any]])
async def get_table_columns(table_name: str):
    """
    Get column information for a specific table.

    Args:
        table_name: Name of the table to inspect

    Returns:
        List of column dictionaries
    """
    try:
        inspector = inspect(engine)

        # Check if table exists
        if table_name not in inspector.get_table_names():
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )

        columns = []
        column_info = inspector.get_columns(table_name)

        for col in column_info:
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "default": col.get("default"),
                "autoincrement": col.get("autoincrement", False)
            })

        return sorted(columns, key=lambda x: x["name"])

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table columns: {str(e)}"
        )

@router.get("/information_schema/tables", response_model=List[Dict[str, Any]])
async def get_information_schema_tables():
    """
    Get database tables using information_schema approach.

    Returns:
        List of tables with their structure
    """
    try:
        tables = []

        # Use SQLAlchemy's information schema query
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'main'
                ORDER BY table_name, ordinal_position
            """))

            rows = result.fetchall()

            # Group by table
            current_table = None
            table_data = []

            for row in rows:
                if row.table_name != current_table:
                    if current_table is not None:
                        tables.append({
                            "table_name": current_table,
                            "columns": table_data
                        })
                    current_table = row.table_name
                    table_data = []

                table_data.append({
                    "name": row.column_name,
                    "type": row.data_type,
                    "nullable": row.is_nullable == "YES",
                    "default": row.column_default
                })

            # Add the last table
            if current_table is not None:
                tables.append({
                    "table_name": current_table,
                    "columns": table_data
                })

        return tables

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Information schema query failed: {str(e)}"
        )

@router.get("/health")
async def database_health():
    """
    Check database connection health.

    Returns:
        Health status of the database connection
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {"status": "healthy", "database": str(engine.url)}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )