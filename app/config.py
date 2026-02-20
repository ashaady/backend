from __future__ import annotations

import os


DATABASE_URL = os.getenv("ACCESS_DATABASE_URL", "sqlite:///./access.db")
ACCESS_BACKEND_API_KEY = os.getenv("ACCESS_BACKEND_API_KEY", "dev-local-access-key")
ACCESS_ALLOWED_ORIGINS = [
    item.strip() for item in os.getenv("ACCESS_ALLOWED_ORIGINS", "*").split(",") if item.strip()
]

