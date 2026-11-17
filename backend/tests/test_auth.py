from __future__ import annotations

import base64
import json

import httpx
import pytest

from backend import auth
from backend.tests.conftest import ALICE, TEST_SECRET, make_token

PROTECTED = [
    ("get", "/api/appointments"),
    ("get", "/api/prescriptions"),
    ("get", "/api/pharmacy/orders"),
    ("get", "/api/users/me"),
    ("get", "/api/specialists"),
    ("post", "/api/emergency/start"),
    ("post", "/api/ai_assistant/chat"),
    ("post", "/api/care/navigate"),
]


def test_valid_token_identifies_the_user(client, alice):
    r = client.get("/api/users/me", headers=alice)
    assert r.status_code == 200
    assert r.json()["id"] == ALICE


@pytest.mark.parametrize("method,path", PROTECTED)
def test_every_data_route_needs_a_token(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def _unsigned(payload: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{enc({'alg': 'none', 'typ': 'JWT'})}.{enc(payload)}."


@pytest.mark.parametrize(
    "token",
    [
        make_token(secret="someone-elses-secret-0123456789abcdef"),
        make_token(exp_in=-60),
        make_token(aud="anon"),
        _unsigned({"sub": ALICE, "aud": "authenticated", "exp": 9999999999}),
        "not-a-token",
        make_token()[:-4] + "AAAA",
    ],
    ids=["wrong-signature", "expired", "wrong-audience", "alg-none", "garbage", "tampered"],
)
def test_bad_tokens_are_rejected(client, token):
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_wrong_scheme_is_rejected(client):
    assert client.get("/api/users/me", headers={"Authorization": f"Basic {make_token()}"}).status_code == 401


def test_token_from_another_project_is_rejected(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    token = make_token(iss="https://other.supabase.co/auth/v1")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_demo_user_must_be_switched_on(client, monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    assert client.get("/api/users/me").status_code == 503  # settings missing: refuse, do not open up

    monkeypatch.setenv("CARECONNECT_ALLOW_DEMO_USER", "1")
    r = client.get("/api/users/me")
    assert r.status_code == 200
    assert r.json()["id"] == "demo-user"


def test_demo_switch_is_ignored_once_sign_in_is_configured(client, monkeypatch):
    monkeypatch.setenv("CARECONNECT_ALLOW_DEMO_USER", "1")
    assert client.get("/api/users/me").status_code == 401


def test_unknown_key_ids_cannot_force_a_refetch_per_request(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    calls = []

    class Reply:
        def raise_for_status(self): ...
        def json(self): return {"keys": [{"kid": "real", "kty": "EC", "crv": "P-256", "x": "AA", "y": "AA"}]}

    monkeypatch.setattr(auth.httpx, "get", lambda *a, **k: calls.append(1) or Reply())
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    for n in range(5):
        token = f"{enc({'alg': 'ES256', 'kid': f'bogus-{n}'})}.{enc({'sub': ALICE})}.c2ln"
        assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert len(calls) == 1


def test_never_trusts_a_token_it_cannot_verify(client, monkeypatch):
    """Asymmetric token, signing keys unreachable: 503, not an unverified decode."""
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.delenv("SUPABASE_JWT_SECRET")

    def unreachable(*args, **kwargs):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(auth.httpx, "get", unreachable)
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    token = f"{enc({'alg': 'ES256', 'kid': 'k1'})}.{enc({'sub': ALICE, 'aud': 'authenticated'})}.c2ln"
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503


def test_hs256_token_is_refused_when_project_has_no_shared_secret(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mine.supabase.co")
    monkeypatch.delenv("SUPABASE_JWT_SECRET")
    token = make_token(secret=TEST_SECRET, iss="https://mine.supabase.co/auth/v1")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
