"""Care plans. SIMULATED: choosing a plan records it and takes no payment.

Subscriptions are written with the service-role key because patients have no write
access to them (a real integration would write here from the payment provider's
webhook instead of on the user's say-so).
"""

from __future__ import annotations

from typing import Optional

import httpx

from backend import config
from backend.models.schemas import Plan
from backend.store.base import NotFound, Unavailable

DEMO_PLANS = [
    Plan(slug="basic", name="Basic", price_cents_monthly=2900, features=["Virtual visits", "Medical records"]),
    Plan(slug="pro", name="Pro", price_cents_monthly=5900,
         features=["Virtual visits", "E-prescriptions", "Specialist chat", "Health coach"]),
    Plan(slug="family", name="Family", price_cents_monthly=9900,
         features=["Everything in Pro", "Up to 6 family members", "Home lab collections"]),
]
_memory_choice: dict[str, str] = {}


def reset() -> None:
    _memory_choice.clear()


def _service(method: str, table: str, **kwargs) -> list[dict]:
    key = config.supabase_service_key()
    if not key:
        raise Unavailable("Plans are not configured (SUPABASE_SERVICE_ROLE_KEY).")
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=representation"}
    try:
        r = httpx.request(method, f"{config.supabase_url()}/rest/v1/{table}", headers=headers, timeout=12.0, **kwargs)
        r.raise_for_status()
        return r.json() if r.content else []
    except Exception as exc:
        raise Unavailable() from exc


def _plan(row: dict) -> Plan:
    return Plan(slug=row["slug"], name=row["name"], price_cents_monthly=row["price_cents_monthly"],
                features=row.get("features") or [])


def list_plans() -> list[Plan]:
    if not config.supabase_configured():
        return list(DEMO_PLANS)
    rows = _service("GET", "plans", params={"select": "slug,name,price_cents_monthly,features",
                                           "order": "price_cents_monthly"})
    return [_plan(r) for r in rows]


def current_plan(user_id: str) -> Optional[Plan]:
    if not config.supabase_configured():
        slug = _memory_choice.get(user_id)
        return next((p for p in DEMO_PLANS if p.slug == slug), None)
    rows = _service("GET", "subscriptions", params={
        "select": "plans(slug,name,price_cents_monthly,features)", "user_id": f"eq.{user_id}",
        "status": "eq.active", "order": "created_at.desc", "limit": 1,
    })
    return _plan(rows[0]["plans"]) if rows and rows[0].get("plans") else None


def choose_plan(user_id: str, slug: str) -> Plan:
    if not config.supabase_configured():
        plan = next((p for p in DEMO_PLANS if p.slug == slug), None)
        if not plan:
            raise NotFound("Plan not found.")
        _memory_choice[user_id] = slug
        return plan
    rows = _service("GET", "plans", params={"select": "id,slug,name,price_cents_monthly,features", "slug": f"eq.{slug}"})
    if not rows:
        raise NotFound("Plan not found.")
    _service("PATCH", "subscriptions", params={"user_id": f"eq.{user_id}", "status": "eq.active"},
             json={"status": "cancelled"})
    _service("POST", "subscriptions", json={"user_id": user_id, "plan_id": rows[0]["id"], "status": "active"})
    return _plan(rows[0])
