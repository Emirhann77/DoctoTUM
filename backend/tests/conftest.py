"""Shared fixtures. Tests never read .env.local and never call Supabase or OpenAI
(the opt-in exception is test_live.py)."""

from __future__ import annotations

import os
import time

os.environ["CARECONNECT_SKIP_DOTENV"] = "1"

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend import auth
from backend.main import app
from backend.services import directory
from backend.store import memory
from backend.utils import rate_limit

TEST_SECRET = "test-secret-not-a-real-key-0123456789"
ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"

_SETTINGS = (
    "SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "OPENAI_API_KEY",
)


def make_token(sub: str = ALICE, *, secret: str = TEST_SECRET, exp_in: int = 3600, **claims) -> str:
    payload = {"sub": sub, "aud": "authenticated", "email": f"{sub[:4]}@example.com",
               "exp": int(time.time()) + exp_in, **claims}
    return jwt.encode(payload, secret, algorithm="HS256")


def as_user(sub: str = ALICE) -> dict:
    return {"Authorization": f"Bearer {make_token(sub)}"}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """In-memory store, token auth with a test secret, mock AI."""
    for name in _SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_SECRET)
    memory.reset()
    rate_limit.reset()
    directory.reset_cache()
    auth.reset_key_cache()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def alice() -> dict:
    return as_user(ALICE)


@pytest.fixture
def bob() -> dict:
    return as_user(BOB)
