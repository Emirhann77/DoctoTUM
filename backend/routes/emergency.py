from __future__ import annotations

import uuid

from fastapi import APIRouter

from backend.database import db
from backend.models.schemas import EmergencyEndRequest, EmergencySession, EmergencyStartRequest

router = APIRouter()


@router.post("/emergency/start", response_model=EmergencySession)
def start_emergency(body: EmergencyStartRequest):
    doctor_id = db.next_emergency_doctor_id()
    if doctor_id is None:
        doctor_id = 1
    wait = db.estimate_wait_minutes()
    return EmergencySession(
        session_id=uuid.uuid4().hex,
        doctor_id=doctor_id,
        status="waiting",
        estimated_wait_minutes=wait,
        video_url="https://example.com/mock-video-room",
    )


@router.post("/emergency/end")
def end_emergency(body: EmergencyEndRequest):
    return {"ok": True, "session_id": body.session_id}
