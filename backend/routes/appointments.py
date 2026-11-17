from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from backend.models.schemas import Appointment, AppointmentCreateRequest
from backend.services import directory
from backend.store import Store, get_store

router = APIRouter()

MAX_DAYS_AHEAD = 365


@router.get("/appointments", response_model=list[Appointment])
def list_appointments(store: Store = Depends(get_store)):
    return store.list_appointments()


@router.post("/appointments", response_model=Appointment, status_code=201)
def create_appointment(body: AppointmentCreateRequest, store: Store = Depends(get_store)):
    start = body.start_time
    if start.tzinfo is None:
        raise HTTPException(status_code=422, detail="start_time must include a timezone.")
    start = start.astimezone(timezone.utc).replace(microsecond=0)
    now = datetime.now(tz=timezone.utc)
    if start <= now:
        raise HTTPException(status_code=422, detail="Choose a time in the future.")
    if start > now + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(status_code=422, detail="Choose a time within the next year.")

    specialist = directory.get_specialist(body.specialist_id)
    if not specialist:
        raise HTTPException(status_code=404, detail="Doctor not found.")
    reason = (body.reason or "").strip() or None
    return store.create_appointment(specialist, start, reason)


@router.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: str, store: Store = Depends(get_store)):
    store.cancel_appointment(appointment_id)
    return {"ok": True}
