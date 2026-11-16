"""Create a confirmed test account with sample prescriptions. Development only.

    python -m backend.scripts.seed_demo

Uses the service-role key from .env.local. Safe to run again: the account and its
prescriptions are reused. The generated password is written to .env.local
(E2E_TEST_EMAIL / E2E_TEST_PASSWORD), which is gitignored, and never printed.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ENV_FILE = Path(".env.local")
DEFAULT_EMAIL = "e2e.patient@careconnect.example"  # reserved TLD: no real mailbox, no email is sent
SAMPLE_PRESCRIPTIONS = [
    ("Lisinopril 10mg", "1 tablet daily", "Take in the morning"),
    ("Metformin 500mg", "1 tablet twice daily", "Take with food"),
    ("Atorvastatin 20mg", "1 tablet daily", "Take before bed"),
]


def _append_env(name: str, value: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    if f"\n{name}=" in f"\n{text}":
        return
    with ENV_FILE.open("a", encoding="utf-8", newline="") as fh:
        fh.write(("" if text.endswith("\n") or not text else "\n") + f"{name}={value}\n")


def main() -> int:
    load_dotenv(ENV_FILE, override=True)
    url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env.local")
        return 1
    email = os.getenv("E2E_TEST_EMAIL") or DEFAULT_EMAIL
    password = os.getenv("E2E_TEST_PASSWORD") or secrets.token_urlsafe(18)
    admin = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    with httpx.Client(timeout=20.0, headers=admin) as http:
        r = http.post(f"{url}/auth/v1/admin/users", json={
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"full_name": "Test Patient"},
        })
        if r.status_code in (200, 201):
            user_id = r.json()["id"]
            print(f"created {email}")
        else:
            users = http.get(f"{url}/auth/v1/admin/users", params={"per_page": 200}).json().get("users", [])
            match = next((u for u in users if u.get("email") == email), None)
            if not match:
                print(f"could not create or find {email}: HTTP {r.status_code} {r.text[:200]}")
                return 1
            user_id = match["id"]
            if not os.getenv("E2E_TEST_PASSWORD"):
                http.put(f"{url}/auth/v1/admin/users/{user_id}", json={"password": password}).raise_for_status()
            print(f"reusing {email}")
        _append_env("E2E_TEST_EMAIL", email)
        _append_env("E2E_TEST_PASSWORD", password)

        rest = f"{url}/rest/v1"
        existing = http.get(f"{rest}/prescriptions", params={"select": "id", "patient_id": f"eq.{user_id}"}).json()
        if existing:
            print(f"{len(existing)} prescriptions already present")
            return 0
        doctor = http.get(f"{rest}/providers", params={
            "select": "id", "specialty": "eq.General Practitioner", "order": "display_name", "limit": 1,
        }).json()
        if not doctor:
            print("no doctors found: apply the migrations first")
            return 1
        r = http.post(f"{rest}/prescriptions", json=[
            {"patient_id": user_id, "prescriber_provider_id": doctor[0]["id"], "medication_name": name,
             "dosage": dosage, "instructions": instructions, "status": "issued"}
            for name, dosage, instructions in SAMPLE_PRESCRIPTIONS
        ])
        r.raise_for_status()
        print(f"issued {len(SAMPLE_PRESCRIPTIONS)} sample prescriptions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
