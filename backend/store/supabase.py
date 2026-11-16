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


def is_uuid(value: str) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _appointment(row: dict) -> Appointment:
    provider = row.get("providers") or {}
    return Appointment(
        id=row["id"],
        specialist_id=row.get("provider_id"),
        specialist_name=provider.get("display_name"),
        specialty=provider.get("specialty"),
        start_time=row["scheduled_at"],
        status="cancelled" if row.get("status") == "cancelled" else "booked",
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
        except httpx.HTTPError as exc:
            raise Unavailable() from exc
        if r.status_code >= 500:
            raise Unavailable()
        if r.status_code >= 400:
            try:
                code = r.json().get("code")
            except ValueError:
                code = None
            if code == "23505":
                raise Conflict()
            if r.status_code in (401, 403) or code == "42501":
                # The token was accepted by us but refused by the database: treat as not theirs.
                raise NotFound()
            raise StoreError("The request could not be completed.")
        return r.json() if r.content else []

    # --- appointments ---
    def list_appointments(self) -> list[Appointment]:
        rows = self._request("GET", "consultations", params={
            "select": _APPOINTMENT_COLS,
            "patient_id": f"eq.{self.user_id}",
            "scheduled_at": "not.is.null",
            "status": "neq.cancelled",
            "order": "scheduled_at.asc",
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
        if not is_uuid(appointment_id):
            raise NotFound("Appointment not found.")
        rows = self._request(
            "PATCH", "consultations", returning=True, json={"status": "cancelled"},
            params={"id": f"eq.{appointment_id}", "patient_id": f"eq.{self.user_id}", "status": "neq.cancelled", "select": "id"},
        )
        if not rows:
            raise NotFound("Appointment not found.")

    # --- prescriptions and orders ---
    def list_prescriptions(self) -> list[Prescription]:
        rows = self._request("GET", "prescriptions", params={
            "select": _PRESCRIPTION_COLS,
            "patient_id": f"eq.{self.user_id}",
            "status": "neq.cancelled",
            "order": "created_at.desc",
        })
        return [_prescription(r) for r in rows]

    def list_orders(self) -> list[PharmacyOrder]:
        rows = self._request("GET", "pharmacy_orders", params={
            "select": _ORDER_COLS, "user_id": f"eq.{self.user_id}", "order": "created_at.desc",
        })
        return [_order(r) for r in rows]

    def create_orders(self, items: list[PharmacyOrderItem]) -> list[PharmacyOrder]:
        rx_ids = {i.prescription_id for i in items if i.prescription_id}
        if rx_ids:
            if not all(is_uuid(i) for i in rx_ids):
                raise NotFound("Prescription not found.")
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
                    "prescription_id": i.prescription_id,
                    "notes": i.notes,
                }
                for i in items
            ],
        )
        return [_order(r) for r in rows]

    def cancel_order(self, order_id: str) -> PharmacyOrder:
        if not is_uuid(order_id):
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
        if not is_uuid(alert_id):
            raise NotFound("Alert not found.")
        rows = self._request(
            "PATCH", "emergency_alerts", returning=True,
            json={"status": "cancelled", "ended_at": datetime.now(tz=timezone.utc).isoformat()},
            params={"id": f"eq.{alert_id}", "user_id": f"eq.{self.user_id}", "select": _ALERT_COLS},
        )
        if not rows:
            raise NotFound("Alert not found.")
        return _alert(rows[0])

    def display_name(self) -> Optional[str]:
        rows = self._request("GET", "profiles", params={"select": "display_name", "id": f"eq.{self.user_id}"})
        return rows[0].get("display_name") if rows else None
