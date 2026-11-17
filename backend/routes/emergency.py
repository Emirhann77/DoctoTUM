from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.models.schemas import EmergencyAlert, EmergencyEndRequest, EmergencyStartRequest
from backend.store import Store, get_store

router = APIRouter()


# Records that the person pressed SOS. It does NOT contact emergency services
# (`dispatched` is always false); the page must tell them to call 112 themselves.
@router.post("/emergency/start", response_model=EmergencyAlert, status_code=201)
def start_emergency(body: EmergencyStartRequest, store: Store = Depends(get_store)):
    location = body.location.model_dump(exclude_none=True) if body.location else None
    return store.start_alert(body.symptoms, body.preferred_language, location or None)


@router.post("/emergency/end", response_model=EmergencyAlert)
def end_emergency(body: EmergencyEndRequest, store: Store = Depends(get_store)):
    return store.end_alert(body.alert_id)
