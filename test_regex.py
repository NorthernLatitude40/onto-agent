#!/usr/bin/env python3
import re

test_string = "url: '/api/v1/auth/me'"
print(f"Test string: {test_string}")

# Current pattern (buggy)
matches_buggy = re.findall(r"url:\s*['\"](/api/v1/[^'\"]+)['\"]", test_string)
print(f"Buggy pattern matches: {matches_buggy}")

# Fixed pattern - use non-capturing group for /api/v1/
matches_fixed = re.findall(r"url:\s*['\"](?:/api/v1/)([^'\"]+)['\"]", test_string)
print(f"Fixed pattern matches: {matches_fixed}")

# Alternative - match the full path and strip /api/v1/
matches_alt = re.findall(r"url:\s*['\"](/api/v1/[^'\"]+)['\"]", test_string)
print(f"Alternative matches: {matches_alt}")