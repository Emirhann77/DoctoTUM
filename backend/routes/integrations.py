from __future__ import annotations

import os

from fastapi import APIRouter

from backend.services.supabase_sync import is_supabase_rest_configured

router = APIRouter()


@router.get("/integrations/status")
def integration_status():
    openai = bool((os.getenv("OPENAI_API_KEY") or "").strip())
    return {
        "supabase_rest_configured": is_supabase_rest_configured(),
        "openai_configured": openai,
        "ai_mode": "openai" if openai else "mock",
        "specialists_source": "supabase" if is_supabase_rest_configured() else "mock_in_memory",
    }
