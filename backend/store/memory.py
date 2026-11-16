"""In-memory Store: tests and keyless local development. Lost on restart."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from backend.models.schemas import (
    Appointment,
    EmergencyAlert,
    PharmacyOrder,
    PharmacyOrderItem,
    Prescription,
    Specialist,
)
from backend.store.base import Conflict, NotFound

SPECIALISTS: list[Specialist] = [
    Specialist(id="1", name="Dr. Ayşe Yılmaz", specialty="General Practitioner", location="Munich",
               country="Germany", languages=["English", "German", "Turkish"], is_available=True),
    Specialist(id="2", name="Dr. Max Müller", specialty="Cardiology", location="Munich",
               country="Germany", languages=["German", "English"], is_available=False),
    Specialist(id="3", name="Dr. Sofia Rossi", specialty="Dermatology", location="Garching",
               country="Germany", languages=["English", "Italian", "German"], is_available=True),
    Specialist(id="4", name="Dr. Elif Kaya", specialty="Emergency Medicine", location="Munich",
               country="Germany", languages=["English", "German", "Turkish"], is_available=True),
    Specialist(id="5", name="Dr. Lucía Fernández", specialty="Psychiatry", location="Munich",
               country="Germany", languages=["Spanish", "English", "German"], is_available=True),
    Specialist(id="6", name="Dr. Camille Laurent", specialty="Pediatrics", location="Garching",
               country="Germany", languages=["French", "English", "German"], is_available=True),
    Specialist(id="7", name="Dr. Jonas Weber", specialty="General Practitioner", location="Garching",
               country="Germany", languages=["German", "English"], is_available=True),
]

# user id -> {record id -> record}
_appointments: dict[str, dict[str, Appointment]] = {}
_prescriptions: dict[str, dict[str, Prescription]] = {}
_orders: dict[str, dict[str, PharmacyOrder]] = {}
_alerts: dict[str, dict[str, EmergencyAlert]] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def reset() -> None:
    for table in (_appointments, _prescriptions, _orders, _alerts):
        table.clear()


def issue_prescription(
    user_id: str, medication: str, dosage: str, instructions: str, prescribed_by: str
) -> Prescription:
    """What a doctor does. Not reachable from the patient API."""
    rx = Prescription(
        id=str(uuid4()), medication=medication, dosage=dosage, instructions=instructions,
        prescribed_by=prescribed_by, status="issued", created_at=_now(),
    )
    _prescriptions.setdefault(user_id, {})[rx.id] = rx
    return rx


def seed_demo_user(user_id: str) -> None:
    if _prescriptions.get(user_id):
        return
    issue_prescription(user_id, "Lisinopril 10mg", "1 tablet daily", "Take in the morning", "Dr. Ayşe Yılmaz")
    issue_prescription(user_id, "Metformin 500mg", "1 tablet twice daily", "Take with food", "Dr. Ayşe Yılmaz")


class MemoryStore:
    def __init__(self, user_id: str, email: Optional[str] = None):
        self.user_id = user_id
        self.email = email

    # --- appointments ---
    def list_appointments(self) -> list[Appointment]:
        mine = _appointments.get(self.user_id, {}).values()
        return sorted((a for a in mine if a.status != "cancelled"), key=lambda a: a.start_time)

    def create_appointment(self, specialist: Specialist, start_time: datetime, reason: Optional[str]) -> Appointment:
        if any(a.start_time == start_time for a in self.list_appointments()):
            raise Conflict("You already have an appointment at that time.")
        appt = Appointment(
            id=str(uuid4()), specialist_id=specialist.id, specialist_name=specialist.name,
            specialty=specialist.specialty, start_time=start_time, status="booked", reason=reason,
        )
        _appointments.setdefault(self.user_id, {})[appt.id] = appt
        return appt

    def cancel_appointment(self, appointment_id: str) -> None:
        appt = _appointments.get(self.user_id, {}).get(appointment_id)
        if not appt or appt.status == "cancelled":
            raise NotFound("Appointment not found.")
        _appointments[self.user_id][appointment_id] = appt.model_copy(update={"status": "cancelled"})

    # --- prescriptions and orders ---
    def list_prescriptions(self) -> list[Prescription]:
        return sorted(_prescriptions.get(self.user_id, {}).values(), key=lambda p: p.created_at, reverse=True)

    def list_orders(self) -> list[PharmacyOrder]:
        return sorted(_orders.get(self.user_id, {}).values(), key=lambda o: o.created_at, reverse=True)

    def create_orders(self, items: list[PharmacyOrderItem]) -> list[PharmacyOrder]:
        mine = _prescriptions.get(self.user_id, {})
        if any(i.prescription_id and i.prescription_id not in mine for i in items):
            raise NotFound("Prescription not found.")
        created = []
        for item in items:
            order = PharmacyOrder(
                id=str(uuid4()), medication_name=item.medication_name, quantity=item.quantity,
                status="requested", prescription_id=item.prescription_id, notes=item.notes, created_at=_now(),
            )
            _orders.setdefault(self.user_id, {})[order.id] = order
            created.append(order)
        return created

    def cancel_order(self, order_id: str) -> PharmacyOrder:
        order = _orders.get(self.user_id, {}).get(order_id)
        if not order:
            raise NotFound("Order not found.")
        if order.status != "requested":
            raise Conflict("This order can no longer be cancelled.")
        updated = order.model_copy(update={"status": "cancelled"})
        _orders[self.user_id][order_id] = updated
        return updated

    # --- emergency ---
    def start_alert(self, symptoms: Optional[str], language: Optional[str], location: Optional[dict]) -> EmergencyAlert:
        alert = EmergencyAlert(alert_id=str(uuid4()), status="active", created_at=_now())
        _alerts.setdefault(self.user_id, {})[alert.alert_id] = alert
        return alert

    def end_alert(self, alert_id: str) -> EmergencyAlert:
        alert = _alerts.get(self.user_id, {}).get(alert_id)
        if not alert:
            raise NotFound("Alert not found.")
        updated = alert.model_copy(update={"status": "cancelled"})
        _alerts[self.user_id][alert_id] = updated
        return updated

    def display_name(self) -> Optional[str]:
        return (self.email or "").split("@")[0] or None
