from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.models.schemas import Prescription
from backend.store import Store, get_store

router = APIRouter()


# Read-only for patients: prescriptions are issued by a doctor, never self-created.
@router.get("/prescriptions", response_model=list[Prescription])
def list_prescriptions(store: Store = Depends(get_store)):
    return store.list_prescriptions()
