"""CORS origins come from CORS_ALLOW_ORIGINS when the app is created (the iOS app and the
hosted web copy depend on this)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import create_app

CAPACITOR = "capacitor://localhost"
WEB = "https://careconnect-web.onrender.com"


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/api/specialists",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_configured_origins_are_allowed_and_others_are_not(monkeypatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", f"{CAPACITOR},{WEB}")
    client = TestClient(create_app())

    for origin in (CAPACITOR, WEB):
        res = _preflight(client, origin)
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == origin

    assert "access-control-allow-origin" not in _preflight(client, "https://evil.example").headers
