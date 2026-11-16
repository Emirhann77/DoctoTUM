from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, Query

from backend.database import db
from backend.models.schemas import Appointment, AppointmentCreateRequest
from backend.services import supabase_sync

router = APIRouter()


@router.get("/appointments", response_model=list[Appointment])
def list_appointments(user_id: int = Query(..., ge=1)):
    return db.list_user_appointments(user_id)


@router.post("/appointments", response_model=Appointment)
def create_appointment(body: AppointmentCreateRequest):
    spec = supabase_sync.get_specialist_unified(body.specialist_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Specialist not found")
    return db.create_appointment(
        body.user_id,
        body.specialist_id,
        body.start_time,
        body.reason,
    )


@router.delete("/appointments/{appointment_id}")
def remove_appointment(appointment_id: str):
    if not db.delete_appointment(appointment_id):
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"ok": True}
