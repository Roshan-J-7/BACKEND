"""
auth_config.py
==============
JWT and auth configuration.
Loaded from .env — never hardcoded.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────
# JWT Settings
# ─────────────────────────────

# Secret used to sign JWT tokens. Set this in .env for production.
# Falls back to a dev-only default if not set.
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "cura-dev-secret-change-in-prod")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_DAYS: int = 7          # Tokens expire after 7 days
