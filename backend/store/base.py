"""The data operations the routes need, independent of where the data lives.

A Store is built for one signed-in user and can only ever touch that user's rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol

from backend.models.schemas import (
    Appointment,
    EmergencyAlert,
    PharmacyOrder,
    PharmacyOrderItem,
    Prescription,
    Specialist,
)


class StoreError(Exception):
    status_code = 500
    message = "Something went wrong."

    def __init__(self, message: Optional[str] = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class NotFound(StoreError):
    status_code = 404
    message = "Not found."


class Conflict(StoreError):
    status_code = 409
    message = "That conflicts with something that already exists."


class Unavailable(StoreError):
    status_code = 503
    message = "The service is temporarily unavailable. Please try again."


class Store(Protocol):
    def list_appointments(self) -> list[Appointment]: ...

    def create_appointment(
        self, specialist: Specialist, start_time: datetime, reason: Optional[str]
    ) -> Appointment: ...

    def cancel_appointment(self, appointment_id: str) -> None: ...

    def list_prescriptions(self) -> list[Prescription]: ...

    def list_orders(self) -> list[PharmacyOrder]: ...

    def create_orders(self, items: list[PharmacyOrderItem]) -> list[PharmacyOrder]: ...

    def cancel_order(self, order_id: str) -> PharmacyOrder: ...

    def start_alert(
        self, symptoms: Optional[str], language: Optional[str], location: Optional[dict]
    ) -> EmergencyAlert: ...

    def end_alert(self, alert_id: str) -> EmergencyAlert: ...

    def display_name(self) -> Optional[str]: ...
