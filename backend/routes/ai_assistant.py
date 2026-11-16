from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import CurrentUser, current_user
from backend.models.schemas import AIChatRequest, AIChatResponse, TriageRequest, TriageResponse
from backend.services import ai_responses
from backend.utils import rate_limit

router = APIRouter()

CHAT_LIMIT_PER_HOUR = 30


@router.post("/ai_assistant/chat", response_model=AIChatResponse)
def ai_chat(body: AIChatRequest, user: CurrentUser = Depends(current_user)):
    rate_limit.check(user.id, "ai", CHAT_LIMIT_PER_HOUR, 3600)
    return ai_responses.chat(body.user_message, body.language)


@router.post("/ai_assistant/triage", response_model=TriageResponse)
def ai_triage(body: TriageRequest, user: CurrentUser = Depends(current_user)):
    rate_limit.check(user.id, "ai", CHAT_LIMIT_PER_HOUR, 3600)
    return ai_responses.triage(body.symptoms, body.age, list(body.known_conditions), body.duration)
