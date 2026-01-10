#!/usr/bin/env python
"""
Generate random secret keys for Flask configuration.
"""

import secrets

print("🔑 Generating secret keys for .env file:")
print()
print(f"SECRET_KEY={secrets.token_urlsafe(32)}")
print(f"JWT_SECRET_KEY={secrets.token_urlsafe(32)}")
print()
print("Copy these values to your .env file!")
