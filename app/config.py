from __future__ import annotations

import os


DATABASE_URL = os.getenv("ACCESS_DATABASE_URL", "sqlite:///./access.db")
ACCESS_BACKEND_API_KEY = os.getenv("ACCESS_BACKEND_API_KEY", "dev-local-access-key")


def _parse_csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ACCESS_ALLOWED_ORIGINS = _parse_csv_env("ACCESS_ALLOWED_ORIGINS", "*")
ACCESS_ALLOWED_ORIGIN_REGEX = os.getenv("ACCESS_ALLOWED_ORIGIN_REGEX")
ACCESS_CORS_ALLOW_CREDENTIALS = _parse_bool_env("ACCESS_CORS_ALLOW_CREDENTIALS", True)
