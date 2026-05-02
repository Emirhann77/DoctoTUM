from __future__ import annotations

from fastapi import APIRouter, Query

from backend.database import db
from backend.models.schemas import Prescription, PrescriptionCreateRequest

router = APIRouter()


@router.get("/prescriptions", response_model=list[Prescription])
def list_prescriptions(user_id: int = Query(..., ge=1)):
    return db.list_user_prescriptions(user_id)


@router.post("/prescriptions", response_model=Prescription)
def add_prescription(body: PrescriptionCreateRequest):
    return db.create_prescription(
        body.user_id,
        body.medication,
        body.dosage,
        body.instructions,
        body.prescribed_by,
    )
