from __future__ import annotations

from fastapi import APIRouter

from backend import config

router = APIRouter()


@router.get("/integrations/status")
def integration_status():
    supabase = config.supabase_configured()
    openai = bool(config.openai_key())
    return {
        "data_store": "supabase" if supabase else "in_memory",
        "auth": "demo_user" if config.demo_user_allowed() else "supabase_token",
        "specialists_source": "supabase" if supabase else "in_memory",
        "ai_mode": "openai" if openai else "mock",
        # kept for the Next.js status page
        "supabase_rest_configured": supabase,
        "openai_configured": openai,
    }
