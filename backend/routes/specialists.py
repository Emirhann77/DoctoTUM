from __future__ import annotations

from fastapi import APIRouter

from backend.services import supabase_sync

router = APIRouter()


@router.get("/specialists", response_model_exclude_none=True)
def list_specialists():
    return supabase_sync.list_specialists_unified()


@router.get("/specialists/available", response_model_exclude_none=True)
def list_available():
    return supabase_sync.list_available_specialists_unified()
