"""The doctor directory.

From the Supabase `providers` table when the project is configured (read with the
service-role key: the directory is the same for everyone and holds no patient data),
otherwise the in-memory demo doctors. The two are never mixed: a booking made against
a demo doctor would not exist in the real database.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import httpx

from backend import config
from backend.models.schemas import Specialist
from backend.store import memory
from backend.store.base import Unavailable

_TTL_SECONDS = 60
_RETRY_AFTER_ERROR_SECONDS = 5
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "url": None, "items": None}


def uses_supabase() -> bool:
    return config.supabase_configured()


def reset_cache() -> None:
    with _lock:
        _cache.update(at=0.0, url=None, items=None)


def _fetch() -> list[Specialist]:
    url, key = config.supabase_url(), config.supabase_service_key()
    if not key:
        raise Unavailable("The doctor directory is not configured (SUPABASE_SERVICE_ROLE_KEY).")
    try:
        r = httpx.get(
            f"{url}/rest/v1/providers",
            params={
                "select": "id,display_name,specialty,is_available,languages,city,country,years_experience,image_url",
                "order": "display_name",
            },
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=12.0,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception as exc:
        raise Unavailable("The doctor directory is unavailable right now.") from exc
    return [
        Specialist(
            id=str(row["id"]),
            name=row.get("display_name") or "Doctor",
            specialty=row.get("specialty") or "General Practitioner",
            location=row.get("city") or "",
            country=row.get("country"),
            languages=row.get("languages") or [],
            is_available=bool(row.get("is_available", True)),
            years_experience=row.get("years_experience"),
            image_url=row.get("image_url"),
        )
        for row in rows
    ]


def list_specialists() -> list[Specialist]:
    if not uses_supabase():
        return list(memory.SPECIALISTS)
    url = config.supabase_url()
    with _lock:
        cached = _cache["items"] if _cache["url"] == url else None
        if cached is not None and time.monotonic() - _cache["at"] < _TTL_SECONDS:
            return list(cached)
    # The network call happens outside the lock so readers never queue behind it.
    try:
        items = _fetch()
    except Unavailable:
        if cached is not None:
            with _lock:  # keep serving the last good list; try again shortly
                _cache["at"] = time.monotonic() - _TTL_SECONDS + _RETRY_AFTER_ERROR_SECONDS
            return list(cached)
        raise
    with _lock:
        _cache.update(items=items, url=url, at=time.monotonic())
    return list(items)


def get_specialist(specialist_id: str) -> Optional[Specialist]:
    return next((s for s in list_specialists() if s.id == str(specialist_id)), None)
