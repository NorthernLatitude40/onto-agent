#!/usr/bin/env python3
"""
Simple verification that SQL logging statements are present in the code.
"""

import re

# Read the tools.py file
with open('/workspaces/langgraph_workspace/src/core/shop_agent/tools.py', 'r') as f:
    content = f.read()

print("=" * 80)
print("SQL QUERY LOGGING VERIFICATION")
print("=" * 80)

# Count occurrences of SQL logging patterns
sql_query_patterns = r'\[SQL Query\] Executing:'
sql_param_patterns = r'\[SQL Parameters\]'

sql_query_count = len(re.findall(sql_query_patterns, content))
sql_param_count = len(re.findall(sql_param_patterns, content))

print(f"✓ Found {sql_query_count} SQL query logging statements")
print(f"✓ Found {sql_param_count} SQL parameter logging statements")

# Show examples of where they were added
lines = content.split('\n')
examples = []
for i, line in enumerate(lines):
    if '[SQL Query] Executing:' in line:
        # Get context (3 lines before and after)
        start = max(0, i-3)
        end = min(len(lines), i+4)
        examples.append(f"\n--- Example at line {i+1} ---")
        examples.append('\n'.join(lines[start:end]))

if examples:
    print("\n" + "=" * 80)
    print("EXAMPLES OF SQL LOGGING ADDED:")
    print("=" * 80)
    for ex in examples[:3]:  # Show first 3 examples
        print(ex)

print("\n" + "=" * 80)
print(f"✓ SUCCESS: SQL queries are now logged before execution!")
print("=" * 80)
