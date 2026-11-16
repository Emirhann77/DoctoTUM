"""Environment-derived settings. Read at call time so tests can change the environment."""

from __future__ import annotations

import os


def _env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def supabase_url() -> str:
    return _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL").rstrip("/")


def supabase_anon_key() -> str:
    return _env("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY")


def supabase_service_key() -> str:
    return _env("SUPABASE_SERVICE_ROLE_KEY")


def supabase_jwt_secret() -> str:
    return _env("SUPABASE_JWT_SECRET")


def supabase_configured() -> bool:
    """True when user data lives in Supabase; False means the in-memory store."""
    return bool(supabase_url() and supabase_anon_key())


def auth_required() -> bool:
    """Tokens are mandatory as soon as there is anything to verify them against."""
    return bool(supabase_url() or supabase_jwt_secret())


def openai_key() -> str:
    return _env("OPENAI_API_KEY")
