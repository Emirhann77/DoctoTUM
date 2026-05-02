"""
Optional: load providers from Supabase Postgres (REST) when service role + URL are set.
Falls back to in-memory mock specialists in database/db.py when not configured or on error.
"""

from __future__ import annotations

import os
from typing import List, Optional

import httpx

from backend.database import db
from backend.models.schemas import Specialist


def _supabase_rest_config() -> tuple[Optional[str], Optional[str]]:
    url = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        return None, None
    return url, key


def is_supabase_rest_configured() -> bool:
    u, k = _supabase_rest_config()
    return bool(u and k)


def fetch_providers_from_supabase() -> Optional[List[Specialist]]:
    cfg = _supabase_rest_config()
    if not cfg[0]:
        return None
    url, key = cfg
    try:
        with httpx.Client(timeout=12.0) as client:
            r = client.get(
                f"{url}/rest/v1/providers",
                params={"select": "id,display_name,specialty,is_available", "order": "display_name"},
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                },
            )
            r.raise_for_status()
            rows = r.json()
    except Exception:
        return None

    if not isinstance(rows, list) or not rows:
        return None

    out: List[Specialist] = []
    for i, row in enumerate(rows):
        pid = row.get("id")
        # Stable int id for UI / booking (demo); uuid string hashed
        if isinstance(pid, str):
            sid = 10_000 + (abs(hash(pid)) % 900_000)
        else:
            sid = int(pid) if pid is not None else 10_000 + i
        name = row.get("display_name") or "Provider"
        spec = row.get("specialty") or "General"
        avail = bool(row.get("is_available", True))
        out.append(
            Specialist(
                id=sid,
                name=name,
                specialty=spec,
                location="Munich",
                languages=["English", "German"],
                is_available=avail,
            )
        )
    return out


def list_specialists_unified() -> List[Specialist]:
    remote = fetch_providers_from_supabase()
    if remote:
        return remote
    return db.list_specialists()


def list_available_specialists_unified() -> List[Specialist]:
    return [s for s in list_specialists_unified() if s.is_available]
