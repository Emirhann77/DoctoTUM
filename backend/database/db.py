from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from backend.models.schemas import Appointment, Prescription, Specialist


@dataclass(frozen=True)
class MockUser:
    id: int
    full_name: str
    email: str


# -----------------------------
# Mock data stores (in-memory)
# -----------------------------

_SPECIALISTS: List[Specialist] = [
    Specialist(
        id=1,
        name="Dr. Ayşe Yılmaz",
        specialty="General Practitioner",
        location="Munich",
        languages=["English", "German", "Turkish"],
        is_available=True,
    ),
    Specialist(
        id=2,
        name="Dr. Max Müller",
        specialty="Cardiology",
        location="Munich",
        languages=["German", "English"],
        is_available=False,
    ),
    Specialist(
        id=3,
        name="Dr. Sofia Rossi",
        specialty="Dermatology",
        location="Garching",
        languages=["English", "Italian", "German"],
        is_available=True,
    ),
    Specialist(
        id=4,
        name="Dr. Elif Kaya",
        specialty="Emergency Medicine",
        location="Munich",
        languages=["English", "German", "Turkish"],
        is_available=True,
    ),
]

_USERS: Dict[int, MockUser] = {
    1: MockUser(id=1, full_name="Demo User", email="demo@example.com"),
    2: MockUser(id=2, full_name="Alex Example", email="alex@example.com"),
}

_APPOINTMENTS: Dict[str, Appointment] = {}
_PRESCRIPTIONS: Dict[str, Prescription] = {}


# -----------------------------
# Specialists
# -----------------------------


def list_specialists() -> List[Specialist]:
    return list(_SPECIALISTS)


def get_specialist_by_id(specialist_id: int) -> Optional[Specialist]:
    return next((s for s in _SPECIALISTS if s.id == specialist_id), None)


def list_available_specialists() -> List[Specialist]:
    return [s for s in _SPECIALISTS if s.is_available]


# -----------------------------
# Appointments
# -----------------------------


def create_appointment(
    user_id: int, specialist_id: int, start_time: datetime, reason: Optional[str]
) -> Appointment:
    appointment_id = uuid4().hex
    appt = Appointment(
        id=appointment_id,
        user_id=user_id,
        specialist_id=specialist_id,
        start_time=start_time,
        status="booked",
        reason=reason,
    )
    _APPOINTMENTS[appointment_id] = appt
    return appt


def list_user_appointments(user_id: int) -> List[Appointment]:
    return [a for a in _APPOINTMENTS.values() if a.user_id == user_id]


def delete_appointment(appointment_id: str) -> bool:
    return _APPOINTMENTS.pop(appointment_id, None) is not None


# -----------------------------
# Prescriptions
# -----------------------------


def list_user_prescriptions(user_id: int) -> List[Prescription]:
    return [p for p in _PRESCRIPTIONS.values() if p.user_id == user_id]


def create_prescription(
    user_id: int, medication: str, dosage: str, instructions: str, prescribed_by: str
) -> Prescription:
    presc_id = uuid4().hex
    presc = Prescription(
        id=presc_id,
        user_id=user_id,
        medication=medication,
        dosage=dosage,
        instructions=instructions,
        prescribed_by=prescribed_by,
        created_at=datetime.now(tz=timezone.utc),
    )
    _PRESCRIPTIONS[presc_id] = presc
    return presc


# -----------------------------
# Users (minimal)
# -----------------------------


def get_user(user_id: int) -> Optional[MockUser]:
    return _USERS.get(user_id)


# -----------------------------
# Emergency availability helpers
# -----------------------------


def list_emergency_doctors() -> List[Specialist]:
    # For now, "Emergency Medicine" specialists are available for emergency consults.
    return [
        s
        for s in _SPECIALISTS
        if s.specialty.lower() in {"emergency medicine"} and s.is_available
    ]


def estimate_wait_minutes() -> int:
    # Simple mock: if we have >1 emergency doctor, lower wait.
    docs = list_emergency_doctors()
    if not docs:
        return 10
    return 2 if len(docs) >= 1 else 5


def next_emergency_doctor_id() -> Optional[int]:
    docs = list_emergency_doctors()
    if not docs:
        return None
    return docs[0].id


def suggested_followup_time() -> datetime:
    return datetime.now(tz=timezone.utc) + timedelta(days=1)

