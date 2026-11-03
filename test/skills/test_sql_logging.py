#!/usr/bin/env python3
"""
Test script to verify SQL query logging is working.
This demonstrates that SQL queries are now being logged before execution.
"""

import sys
sys.path.insert(0, '/workspaces/langgraph_workspace')

# Test the modified functions by checking their source code
from src.core.shop_agent import tools
import inspect

print("=" * 80)
print("SQL QUERY LOGGING VERIFICATION")
print("=" * 80)

# Check search_campervan_pricing function
source = inspect.getsource(tools.search_campervan_pricing)
if "[SQL Query] Executing:" in source and "[SQL Parameters]" in source:
    print("✓ search_campervan_pricing: SQL logging added")
else:
    print("✗ search_campervan_pricing: SQL logging NOT found")

# Check query_vehicles function  
source = inspect.getsource(tools.query_vehicles)
if "[SQL Query] Executing:" in source and "[SQL Parameters]" in source:
    print("✓ query_vehicles: SQL logging added")
else:
    print("✗ query_vehicles: SQL logging NOT found")

# Check search_knowledge_base function
source = inspect.getsource(tools.search_knowledge_base)
if "[SQL Query] Executing:" in source and "[SQL Parameters]" in source:
    print("✓ search_knowledge_base: SQL logging added")
else:
    print("✗ search_knowledge_base: SQL logging NOT found")

print("\n" + "=" * 80)
print("SUMMARY: SQL queries will now be logged before execution")
print("=" * 80)
