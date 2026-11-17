"""Supabase Store: PostgREST called *as the signed-in user*.

Requests carry the project's anon key and the user's own access token, so row-level
security decides what they can see and change. The service-role key is never used
for user data; a bug here cannot leak another person's rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from fastapi import HTTPException

from backend import config
from backend.models.schemas import (
    Appointment,
    EmergencyAlert,
    PharmacyOrder,
    PharmacyOrderItem,
    Prescription,
    Specialist,
)
from backend.store.base import Conflict, NotFound, StoreError, Unavailable

_client = httpx.Client(timeout=12.0)

_APPOINTMENT_COLS = "id,scheduled_at,status,reason,provider_id,providers(display_name,specialty)"
_PRESCRIPTION_COLS = "id,medication_name,dosage,instructions,status,created_at,providers(display_name)"
_ORDER_COLS = "id,medication_name,quantity,status,prescription_id,notes,created_at"
_ALERT_COLS = "id,status,created_at"


def canonical_uuid(value: object) -> Optional[str]:
    """Lower-case hyphenated form, or None if it is not a UUID. Ids are compared as
    strings with what the database returns, so they are normalised once, here."""
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _appointment(row: dict) -> Appointment:
    provider = row.get("providers") or {}
    return Appointment(
        id=row["id"],
        specialist_id=row.get("provider_id"),
        specialist_name=provider.get("display_name"),
        specialty=provider.get("specialty"),
        start_time=row["scheduled_at"],
        status="booked" if row.get("status") == "queued" else row.get("status") or "booked",
        reason=row.get("reason"),
    )


def _prescription(row: dict) -> Prescription:
    return Prescription(
        id=row["id"],
        medication=row["medication_name"],
        dosage=row.get("dosage"),
        instructions=row.get("instructions"),
        prescribed_by=(row.get("providers") or {}).get("display_name"),
        status=row.get("status") or "issued",
        created_at=row["created_at"],
    )


def _order(row: dict) -> PharmacyOrder:
    return PharmacyOrder(**{k: row.get(k) for k in _ORDER_COLS.split(",")})


def _alert(row: dict) -> EmergencyAlert:
    return EmergencyAlert(alert_id=row["id"], status=row["status"], created_at=row["created_at"])


class SupabaseStore:
    def __init__(self, user_id: str, token: str):
        self.user_id = user_id
        self._base = f"{config.supabase_url()}/rest/v1"
        self._headers = {
            "apikey": config.supabase_anon_key(),
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str, *, params: dict, json: Any = None, returning: bool = False) -> list[dict]:
        headers = dict(self._headers)
        if returning:
            headers["Prefer"] = "return=representation"
        try:
            r = _client.request(method, f"{self._base}/{table}", params=params, json=json, headers=headers)
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            raise Unavailable() from exc
        if r.status_code >= 500 or r.status_code == 429:
            raise Unavailable()
        if r.status_code >= 400:
            raise self._error(r)
        if not r.content:
            return []
        try:
            body = r.json()
        except ValueError as exc:
            raise Unavailable() from exc
        return body if isinstance(body, list) else [body]

    @staticmethod
    def _error(r: httpx.Response) -> Exception:
        """PostgREST / Postgres error -> the exception the routes understand."""
        try:
            body = r.json()
        except ValueError:
            body = None
        code = body.get("code") if isinstance(body, dict) else None
        if r.status_code == 401 or (code or "").startswith("PGRST3"):
            # We verified the token but the database no longer accepts it (expired mid-request).
            return HTTPException(status_code=401, detail="Sign in to continue",
                                 headers={"WWW-Authenticate": "Bearer"})
        if code == "23505":
            return Conflict()
        if code == "23503":  # a row this one points at is gone
            return NotFound()
        if code == "42501" or r.status_code == 403:  # row-level security said no
            return NotFound()
        if code in ("23514", "23502", "22P02", "22007", "22008") or r.status_code == 400:
            return HTTPException(status_code=422, detail="That request is not valid.")
        return StoreError("The request could not be completed.")

    # --- appointments ---
    def list_appointments(self) -> list[Appointment]:
        rows = self._request("GET", "consultations", params={
            "select": _APPOINTMENT_COLS,
            "patient_id": f"eq.{self.user_id}",
            "scheduled_at": "not.is.null",
            "status": "eq.queued",
            "order": "scheduled_at.asc,id.asc",
        })
        return [_appointment(r) for r in rows]

    def create_appointment(self, specialist: Specialist, start_time: datetime, reason: Optional[str]) -> Appointment:
        try:
            rows = self._request(
                "POST", "consultations", params={"select": _APPOINTMENT_COLS}, returning=True,
                json={
                    "patient_id": self.user_id,
                    "provider_id": specialist.id,
                    "scheduled_at": start_time.astimezone(timezone.utc).isoformat(),
                    "reason": reason,
                    "status": "queued",
                },
            )
        except Conflict:
            raise Conflict("You already have an appointment at that time.") from None
        return _appointment(rows[0])

    def cancel_appointment(self, appointment_id: str) -> None:
        appointment_id = canonical_uuid(appointment_id)
        if not appointment_id:
            raise NotFound("Appointment not found.")
        rows = self._request(
            "PATCH", "consultations", returning=True, json={"status": "cancelled"},
            params={"id": f"eq.{appointment_id}", "patient_id": f"eq.{self.user_id}", "status": "eq.queued", "select": "id"},
        )
        if not rows:
            raise NotFound("Appointment not found.")

    # --- prescriptions and orders ---
    def list_prescriptions(self) -> list[Prescription]:
        rows = self._request("GET", "prescriptions", params={
            "select": _PRESCRIPTION_COLS,
            "patient_id": f"eq.{self.user_id}",
            "status": "in.(pending,issued,filled)",
            "order": "created_at.desc,id.asc",
        })
        return [_prescription(r) for r in rows]

    def list_orders(self) -> list[PharmacyOrder]:
        rows = self._request("GET", "pharmacy_orders", params={
            "select": _ORDER_COLS, "user_id": f"eq.{self.user_id}", "order": "created_at.desc,id.asc",
        })
        return [_order(r) for r in rows]

    def create_orders(self, items: list[PharmacyOrderItem]) -> list[PharmacyOrder]:
        rx_by_item = [canonical_uuid(i.prescription_id) if i.prescription_id else None for i in items]
        if any(i.prescription_id and not rx for i, rx in zip(items, rx_by_item)):
            raise NotFound("Prescription not found.")
        rx_ids = {rx for rx in rx_by_item if rx}
        if rx_ids:
            found = self._request("GET", "prescriptions", params={
                "select": "id", "id": f"in.({','.join(sorted(rx_ids))})", "patient_id": f"eq.{self.user_id}",
            })
            if {r["id"] for r in found} != rx_ids:
                raise NotFound("Prescription not found.")
        rows = self._request(
            "POST", "pharmacy_orders", params={"select": _ORDER_COLS}, returning=True,
            json=[
                {
                    "user_id": self.user_id,
                    "medication_name": i.medication_name,
                    "quantity": i.quantity,
                    "prescription_id": rx,
                    "notes": i.notes,
                }
                for i, rx in zip(items, rx_by_item)
            ],
        )
        return [_order(r) for r in rows]

    def cancel_order(self, order_id: str) -> PharmacyOrder:
        order_id = canonical_uuid(order_id)
        if not order_id:
            raise NotFound("Order not found.")
        mine = {"id": f"eq.{order_id}", "user_id": f"eq.{self.user_id}", "select": _ORDER_COLS}
        rows = self._request(
            "PATCH", "pharmacy_orders", returning=True, json={"status": "cancelled"},
            params={**mine, "status": "eq.requested"},
        )
        if rows:
            return _order(rows[0])
        if self._request("GET", "pharmacy_orders", params=mine):
            raise Conflict("This order can no longer be cancelled.")
        raise NotFound("Order not found.")

    # --- emergency ---
    def start_alert(self, symptoms: Optional[str], language: Optional[str], location: Optional[dict]) -> EmergencyAlert:
        rows = self._request(
            "POST", "emergency_alerts", params={"select": _ALERT_COLS}, returning=True,
            json={"user_id": self.user_id, "symptoms": symptoms, "language": language, "location": location},
        )
        return _alert(rows[0])

    def end_alert(self, alert_id: str) -> EmergencyAlert:
        alert_id = canonical_uuid(alert_id)
        if not alert_id:
            raise NotFound("Alert not found.")
        rows = self._request(
            "PATCH", "emergency_alerts", returning=True,
            json={"status": "cancelled", "ended_at": datetime.now(tz=timezone.utc).isoformat()},
            params={"id": f"eq.{alert_id}", "user_id": f"eq.{self.user_id}", "status": "eq.active", "select": _ALERT_COLS},
        )
        if not rows:
            raise NotFound("Alert not found.")
        return _alert(rows[0])

    def display_name(self) -> Optional[str]:
        rows = self._request("GET", "profiles", params={"select": "display_name", "id": f"eq.{self.user_id}"})
        return rows[0].get("display_name") if rows else None
