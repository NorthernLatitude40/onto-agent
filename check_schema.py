#!/usr/bin/env python3
"""Check database schema for sys_user table"""

from src.common.database import engine
from sqlalchemy import inspect

insp = inspect(engine)
print('Tables:', insp.get_table_names())
print('\nColumns in sys_user:')
for col in insp.get_columns('sys_user'):
    print(f'  {col["name"]}: {col["type"]}')