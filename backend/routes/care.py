from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import CareNavigateRequest, CareNavigateResponse
from backend.services import care_navigator, supabase_sync

router = APIRouter()


@router.get("/care/rules")
def care_rules():
    """The rule set the navigator runs on (same file the static UI falls back to)."""
    return care_navigator.load_rules()


@router.post("/care/navigate", response_model=CareNavigateResponse)
def navigate(body: CareNavigateRequest):
    outcome = care_navigator.evaluate(
        symptoms=[s.strip() for s in body.symptoms],
        severity=body.severity,
        duration=body.duration,
        age=body.age,
        description=body.description,
        known_conditions=body.known_conditions,
    )

    match_language = (body.preferred_consult_language or body.language or "").strip().lower() or None
    matches = []
    if outcome["urgency"] != "emergency":
        matches = care_navigator.rank_specialists(
            supabase_sync.list_specialists_unified(),
            specialty=outcome["specialty_slug"],
            language=match_language or "",
            city=(body.location.city or "") if body.location else "",
        )
    return CareNavigateResponse(**outcome, match_language=match_language, matches=matches)
