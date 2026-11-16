"""Opt-in checks against the real Supabase project in .env.local.

    RUN_LIVE=1 python -m pytest backend/tests/test_live.py -q

Needs the test account from `python -m backend.scripts.seed_demo`. Creates one
throwaway second user and deletes it (and everything these tests wrote) afterwards.
Makes no OpenAI calls.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.skipif(not os.getenv("RUN_LIVE"), reason="set RUN_LIVE=1 to run against Supabase")

ENV = {k: v for k, v in dotenv_values(".env.local").items() if v}


@pytest.fixture(autouse=True)
def live_environment(clean_environment, monkeypatch):
    """Replace the unit-test environment with the real project, minus OpenAI."""
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    for name, value in ENV.items():
        if name != "OPENAI_API_KEY":
            monkeypatch.setenv(name, value)


def _sign_in(email: str, password: str) -> dict:
    r = httpx.post(
        f"{ENV['SUPABASE_URL']}/auth/v1/token", params={"grant_type": "password"},
        headers={"apikey": ENV["NEXT_PUBLIC_SUPABASE_ANON_KEY"]},
        json={"email": email, "password": password}, timeout=20.0,
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin():
    key = ENV["SUPABASE_SERVICE_ROLE_KEY"]
    with httpx.Client(timeout=20.0, headers={"apikey": key, "Authorization": f"Bearer {key}"}) as http:
        yield http


@pytest.fixture(scope="module")
def patient():
    return _sign_in(ENV["E2E_TEST_EMAIL"], ENV["E2E_TEST_PASSWORD"])


@pytest.fixture(scope="module")
def stranger(admin):
    email, password = f"e2e.stranger.{secrets.token_hex(4)}@careconnect.example", secrets.token_urlsafe(18)
    r = admin.post(f"{ENV['SUPABASE_URL']}/auth/v1/admin/users",
                   json={"email": email, "password": password, "email_confirm": True})
    r.raise_for_status()
    try:
        yield _sign_in(email, password)
    finally:
        admin.delete(f"{ENV['SUPABASE_URL']}/auth/v1/admin/users/{r.json()['id']}")


@pytest.fixture
def client():
    return TestClient(app)


def _slot(days: int) -> str:
    d = datetime.now(tz=timezone.utc) + timedelta(days=days)
    return d.replace(hour=3, minute=17, second=0, microsecond=0).isoformat()


def test_real_token_is_verified_and_profile_exists(client, patient):
    me = client.get("/api/users/me", headers=patient)
    assert me.status_code == 200
    assert me.json()["email"] == ENV["E2E_TEST_EMAIL"]
    assert me.json()["display_name"] == "Test Patient"  # created by the signup trigger


def test_forged_token_for_the_real_project_is_rejected(client):
    from jose import jwt

    forged = jwt.encode({"sub": "x", "aud": "authenticated", "iss": f"{ENV['SUPABASE_URL']}/auth/v1",
                         "exp": 9999999999}, "guess", algorithm="HS256")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_directory_comes_from_the_database(client, patient):
    doctors = client.get("/api/specialists", headers=patient).json()
    assert len(doctors) >= 10
    assert all(len(d["id"]) == 36 for d in doctors)
    assert any("Turkish" in d["languages"] for d in doctors)


def test_appointment_lifecycle_and_isolation(client, patient, stranger):
    doctor = client.get("/api/specialists", headers=patient).json()[0]
    when = _slot(200)
    for stale in client.get("/api/appointments", headers=patient).json():
        if stale["reason"] == "live test":
            client.delete(f"/api/appointments/{stale['id']}", headers=patient)

    r = client.post("/api/appointments", headers=patient,
                    json={"specialist_id": doctor["id"], "start_time": when, "reason": "live test"})
    assert r.status_code == 201, r.text
    appt = r.json()
    try:
        assert appt["specialist_name"] == doctor["name"]
        assert appt["id"] in [a["id"] for a in client.get("/api/appointments", headers=patient).json()]

        dup = client.post("/api/appointments", headers=patient,
                          json={"specialist_id": doctor["id"], "start_time": when, "reason": "live test"})
        assert dup.status_code == 409

        assert client.get("/api/appointments", headers=stranger).json() == []
        assert client.delete(f"/api/appointments/{appt['id']}", headers=stranger).status_code == 404
    finally:
        assert client.delete(f"/api/appointments/{appt['id']}", headers=patient).status_code == 200
    assert appt["id"] not in [a["id"] for a in client.get("/api/appointments", headers=patient).json()]


def test_unknown_doctor_is_404(client, patient):
    r = client.post("/api/appointments", headers=patient, json={
        "specialist_id": "00000000-0000-4000-8000-000000000000", "start_time": _slot(201)})
    assert r.status_code == 404


def test_prescriptions_orders_and_isolation(client, patient, stranger, admin):
    rx = client.get("/api/prescriptions", headers=patient).json()
    assert len(rx) >= 3 and rx[0]["prescribed_by"]
    assert client.get("/api/prescriptions", headers=stranger).json() == []

    item = {"medication_name": rx[0]["medication"], "prescription_id": rx[0]["id"], "quantity": 1, "notes": "live test"}
    assert client.post("/api/pharmacy/orders", headers=stranger, json={"items": [item]}).status_code == 404

    r = client.post("/api/pharmacy/orders", headers=patient, json={"items": [item]})
    assert r.status_code == 201, r.text
    order = r.json()[0]
    try:
        assert client.get("/api/pharmacy/orders", headers=stranger).json() == []
        assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=stranger).status_code == 404
        assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=patient).json()["status"] == "cancelled"
        assert client.post(f"/api/pharmacy/orders/{order['id']}/cancel", headers=patient).status_code == 409
    finally:
        admin.delete(f"{ENV['SUPABASE_URL']}/rest/v1/pharmacy_orders", params={"id": f"eq.{order['id']}"})


def test_sos_log_and_isolation(client, patient, stranger, admin):
    r = client.post("/api/emergency/start", headers=patient,
                    json={"symptoms": "live test", "preferred_language": "en", "location": {"city": "Munich"}})
    assert r.status_code == 201, r.text
    alert = r.json()
    try:
        assert alert["dispatched"] is False
        assert client.post("/api/emergency/end", headers=stranger, json={"alert_id": alert["alert_id"]}).status_code == 404
        ended = client.post("/api/emergency/end", headers=patient, json={"alert_id": alert["alert_id"]})
        assert ended.json()["status"] == "cancelled"
    finally:
        admin.delete(f"{ENV['SUPABASE_URL']}/rest/v1/emergency_alerts", params={"id": f"eq.{alert['alert_id']}"})


def test_patient_cannot_write_prescriptions_or_doctors_directly(patient, admin):
    """Row-level security, checked by talking to the database API as the patient."""
    base = f"{ENV['SUPABASE_URL']}/rest/v1"
    headers = {**patient, "apikey": ENV["NEXT_PUBLIC_SUPABASE_ANON_KEY"], "Prefer": "return=representation"}
    doctor = admin.get(f"{base}/providers", params={"select": "id", "limit": 1}).json()[0]["id"]
    me = httpx.get(f"{ENV['SUPABASE_URL']}/auth/v1/user", headers=headers, timeout=20).json()["id"]

    forged = httpx.post(f"{base}/prescriptions", headers=headers, timeout=20, json={
        "patient_id": me, "prescriber_provider_id": doctor, "medication_name": "Oxycodone"})
    assert forged.status_code in (401, 403)

    renamed = httpx.patch(f"{base}/providers", headers=headers, timeout=20,
                          params={"id": f"eq.{doctor}"}, json={"display_name": "Hacked"})
    assert renamed.status_code in (200, 204, 401, 403)
    assert renamed.status_code >= 400 or renamed.json() == []
