#!/usr/bin/env python3
from pathlib import Path
import re

frontend_dir = '../miniprogram-1/miniprogram'
ts_files = list(Path(frontend_dir).rglob('*.ts'))
print(f'Found {len(ts_files)} .ts files')

# Check a few files
for ts_file in list(ts_files)[:5]:
    print(f'\nChecking: {ts_file}')
    with open(ts_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match url: '/api/v1/...' or url: "/api/v1/..."
    matches = re.findall(r"url:\s*['\"](/api/v1/[^'\"]+)['\"]", content)
    print(f'  Found {len(matches)} API calls')
    for match in matches:
        print(f'    - {match}')