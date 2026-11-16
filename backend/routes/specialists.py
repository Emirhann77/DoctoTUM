from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import current_user
from backend.models.schemas import Specialist
from backend.services import directory

router = APIRouter(dependencies=[Depends(current_user)])


@router.get("/specialists", response_model=list[Specialist], response_model_exclude_none=True)
def list_specialists():
    return directory.list_specialists()


@router.get("/specialists/available", response_model=list[Specialist], response_model_exclude_none=True)
def list_available():
    return [s for s in directory.list_specialists() if s.is_available]
